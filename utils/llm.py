"""One LLM interface over Google Gemini (default) and OpenAI.

Every structured call goes through `LLMClient.structured()`, which:
  1. asks the provider for JSON matching a Pydantic schema,
  2. validates it into the Pydantic model (plus an optional business-rule `check`),
  3. on failure, re-asks with the exact validation error as feedback,
  4. raises a clear LLMError after `max_validation_retries` repairs.
Transport errors (429 / 5xx / timeouts) are retried by the SDKs and, for
streaming, by tenacity.
"""
from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from utils.config import ConfigError, Settings
from utils.costs import CostTracker

T = TypeVar("T", bound=BaseModel)
Check = Callable[[BaseModel], Optional[str]]


class LLMError(RuntimeError):
    """Non-recoverable LLM failure (safety block, repeated invalid output, bad config)."""


class OutputValidationError(Exception):
    """The model's output did not match the schema. Triggers a repair attempt."""


@dataclass
class TextResult:
    text: str
    truncated: bool


def summarize_validation_error(exc: ValidationError, limit: int = 12) -> str:
    lines = []
    for err in exc.errors()[:limit]:
        loc = ".".join(str(p) for p in err.get("loc", ())) or "(root)"
        lines.append(f"- {loc}: {err.get('msg')}")
    extra = len(exc.errors()) - limit
    if extra > 0:
        lines.append(f"- ... and {extra} more")
    return "\n".join(lines)


class LLMClient(ABC):
    provider: str = "base"

    def __init__(self, tracker: CostTracker, max_validation_retries: int = 2):
        self.tracker = tracker
        self.max_validation_retries = max_validation_retries
        # Progress messages such as "model X busy; switching to Y". The orchestrator wires this to the UI.
        self.notify: Callable[[str], None] = lambda _message: None

    # ---- public API -------------------------------------------------------
    def structured(
        self,
        *,
        agent: str,
        system: str,
        user: str,
        schema: type[T],
        model: str,
        effort: str,
        max_tokens: int = 16000,
        check: Check | None = None,
    ) -> T:
        attempts = self.max_validation_retries + 1
        feedback: str | None = None
        for _ in range(attempts):
            prompt = user
            if feedback:
                prompt = (
                    f"{user}\n\n<previous_attempt_feedback>\n"
                    f"Your previous response was rejected for these reasons:\n{feedback}\n"
                    "Fix every problem and respond again with the complete output.\n"
                    "</previous_attempt_feedback>"
                )
            try:
                result = self._structured_once(
                    agent=agent, system=system, user=prompt, schema=schema,
                    model=model, effort=effort, max_tokens=max_tokens,
                )
            except OutputValidationError as exc:
                feedback = str(exc)
                continue
            problem = check(result) if check else None
            if problem:
                feedback = problem
                continue
            return result
        raise LLMError(
            f"[{agent}] could not get a valid {schema.__name__} after {attempts} attempts.\n"
            f"Last problem:\n{feedback}"
        )

    def text(self, *, agent: str, system: str, user: str, model: str, effort: str,
             max_tokens: int = 64000) -> TextResult:
        return self._text_once(agent=agent, system=system, user=user, model=model,
                               effort=effort, max_tokens=max_tokens)

    # ---- provider hooks ---------------------------------------------------
    @abstractmethod
    def _structured_once(self, *, agent: str, system: str, user: str, schema: type[T],
                         model: str, effort: str, max_tokens: int) -> T: ...

    @abstractmethod
    def _text_once(self, *, agent: str, system: str, user: str, model: str, effort: str,
                   max_tokens: int) -> TextResult: ...


# =========================================================================== Gemini
RETRYABLE_STATUS = (408, 429, 500, 502, 503, 504)
# The SDK's own HTTP retries skip 429: a daily quota can't succeed for hours, so 429s are
# classified below (short per-minute limits are retried by tenacity; daily limits fail fast).
SDK_RETRY_STATUS = (408, 500, 502, 503, 504)
LONG_RETRY_DELAY_S = 120
EFFORT_TO_THINKING_LEVEL = {
    "minimal": "MINIMAL", "low": "LOW", "medium": "MEDIUM", "high": "HIGH", "xhigh": "XHIGH", "max": "XHIGH",
}
BLOCKED_FINISH_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "IMAGE_SAFETY"}


def _gemini_transient(exc: BaseException) -> bool:
    from google.genai import errors

    if not isinstance(exc, errors.APIError) or getattr(exc, "code", None) not in RETRYABLE_STATUS:
        return False
    return not (exc.code == 429 and quota_details(exc)["long"])


def quota_details(exc: BaseException) -> dict[str, Any]:
    """Pull the useful bits out of a Gemini 429 RESOURCE_EXHAUSTED error."""
    text = str(exc)
    delay = re.search(r"retryDelay'?:\s*'(\d+(?:\.\d+)?)s'", text)
    limit = re.search(r"limit:\s*(\d+)", text)
    model = re.search(r"model:\s*([\w.\-]+)", text)
    seconds = float(delay.group(1)) if delay else None
    per_day = "PerDay" in text or "per day" in text.lower()
    return {
        "retry_seconds": seconds,
        "limit": int(limit.group(1)) if limit else None,
        "model": model.group(1) if model else None,
        "per_day": per_day,
        "free_tier": "free_tier" in text.lower() or "free tier" in text.lower(),
        "long": per_day or (seconds is not None and seconds > LONG_RETRY_DELAY_S),
    }


def quota_message(exc: BaseException, model: str) -> str:
    q = quota_details(exc)
    model = q["model"] or model
    tier = "free-tier " if q["free_tier"] else ""
    period = "daily" if q["per_day"] else "rate"
    limit = f" ({q['limit']} requests per {'day' if q['per_day'] else 'period'})" if q["limit"] else ""
    when = ""
    if q["retry_seconds"]:
        hours, minutes = divmod(int(q["retry_seconds"]) // 60, 60)
        when = f" It resets in about {hours}h {minutes}m." if hours else f" It resets in about {minutes} min."
    return (
        f"Gemini {tier}{period} quota reached for {model}{limit}.{when} "
        "Each model has its own quota: set GEMINI_MODEL in .env to another model (e.g. gemini-3.5-flash-lite) "
        "and restart the backend, or enable billing in Google AI Studio."
    )


def _finish_reason(resp: Any) -> str | None:
    candidates = getattr(resp, "candidates", None) or []
    if not candidates or candidates[0].finish_reason is None:
        return None
    reason = candidates[0].finish_reason
    return getattr(reason, "name", str(reason))


class GeminiLLM(LLMClient):
    """Google Gemini via the official `google-genai` SDK.

    Structured calls use `response_mime_type="application/json"` + `response_schema=<PydanticModel>`;
    the JSON is then validated into the same Pydantic model, so a malformed reply triggers a repair.
    `client` can be injected (the tests pass a fake).
    """

    provider = "gemini"

    def __init__(self, tracker: CostTracker, max_validation_retries: int = 2, client: Any = None):
        super().__init__(tracker, max_validation_retries)
        from google.genai import types

        self._types = types
        if client is None:
            if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
                raise ConfigError("Set GEMINI_API_KEY in .env to use LLM_PROVIDER=gemini.")
            from google import genai

            client = genai.Client(  # reads GEMINI_API_KEY from the environment
                http_options=types.HttpOptions(
                    retry_options=types.HttpRetryOptions(
                        attempts=5, initial_delay=2.0, max_delay=30.0,
                        http_status_codes=list(SDK_RETRY_STATUS),
                    )
                )
            )
        self.client = client
        self.use_thinking_level = True
        self._current_model = ""

    # ---- helpers ----------------------------------------------------------
    def _config(self, *, system: str, effort: str, max_tokens: int, schema: type[BaseModel] | None = None):
        kwargs: dict[str, Any] = {"system_instruction": system, "max_output_tokens": max_tokens}
        if schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_schema"] = schema
        if self.use_thinking_level:
            level = EFFORT_TO_THINKING_LEVEL.get(effort, "MEDIUM")
            kwargs["thinking_config"] = self._types.ThinkingConfig(thinking_level=level)
        return self._types.GenerateContentConfig(**kwargs)

    def _with_thinking_guard(self, call: Callable[[], Any]) -> Any:
        """Some models don't accept `thinking_level`; if the API rejects it, retry once without it."""
        from google.genai import errors

        try:
            try:
                return call()
            except errors.ClientError as exc:
                if self.use_thinking_level and exc.code == 400 and "thinking" in str(exc).lower():
                    self.use_thinking_level = False
                    return call()
                raise
        except errors.ClientError as exc:
            if exc.code == 429 and quota_details(exc)["long"]:
                raise LLMError(quota_message(exc, self._current_model)) from exc
            raise

    def _record(self, agent: str, model: str, usage: Any) -> None:
        if usage is None:
            return
        input_tokens = usage.prompt_token_count or 0
        # Thinking tokens are billed as output.
        output_tokens = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
        self.tracker.add(agent, model, input_tokens, output_tokens)

    def _check_blocked(self, agent: str, resp: Any) -> None:
        feedback = getattr(resp, "prompt_feedback", None)
        block = getattr(feedback, "block_reason", None) if feedback else None
        if block:
            raise LLMError(f"[{agent}] Gemini blocked the prompt ({getattr(block, 'name', block)}).")
        reason = _finish_reason(resp)
        if reason in BLOCKED_FINISH_REASONS:
            raise LLMError(f"[{agent}] Gemini stopped the response for safety reasons ({reason}).")

    # ---- provider hooks ---------------------------------------------------
    @retry(retry=retry_if_exception(_gemini_transient), stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=30), reraise=True)
    def _structured_once(self, *, agent, system, user, schema, model, effort, max_tokens):
        self._current_model = model
        resp = self._with_thinking_guard(lambda: self.client.models.generate_content(
            model=model, contents=user,
            config=self._config(system=system, effort=effort, max_tokens=max_tokens, schema=schema),
        ))
        self._record(agent, model, getattr(resp, "usage_metadata", None))
        self._check_blocked(agent, resp)
        if _finish_reason(resp) == "MAX_TOKENS":
            raise OutputValidationError("Output was cut off at the token limit. Be more concise.")

        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        text = resp.text or ""
        if not text.strip():
            raise OutputValidationError("The model returned an empty response.")
        try:
            return schema.model_validate_json(text)
        except ValidationError as exc:
            raise OutputValidationError(summarize_validation_error(exc)) from exc

    @retry(retry=retry_if_exception(_gemini_transient), stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=30), reraise=True)
    def _text_once(self, *, agent, system, user, model, effort, max_tokens):
        self._current_model = model

        def stream():
            parts: list[str] = []
            usage, last = None, None
            for chunk in self.client.models.generate_content_stream(
                model=model, contents=user,
                config=self._config(system=system, effort=effort, max_tokens=max_tokens),
            ):
                if chunk.text:
                    parts.append(chunk.text)
                if getattr(chunk, "usage_metadata", None):
                    usage = chunk.usage_metadata
                if getattr(chunk, "candidates", None):
                    last = chunk
            return "".join(parts), usage, last

        text, usage, last = self._with_thinking_guard(stream)
        self._record(agent, model, usage)
        if last is not None:
            self._check_blocked(agent, last)
        return TextResult(text=text, truncated=last is not None and _finish_reason(last) == "MAX_TOKENS")


# =========================================================================== OpenAI
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ModelUnavailable(Exception):
    """One model can't serve the request right now; the next fallback model should be tried."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def upstream_reason(exc: BaseException) -> str:
    """OpenRouter wraps provider errors as 'Provider returned error'; the real reason is in metadata.raw."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error", body)
        meta = err.get("metadata") if isinstance(err, dict) else None
        if isinstance(meta, dict):
            raw = meta.get("raw")
            provider = meta.get("provider_name")
            if raw:
                text = raw if isinstance(raw, str) else json.dumps(raw)
                return (f"{provider}: " if provider else "") + text.strip()[:200]
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:200]
    return str(exc).splitlines()[0][:200]


class OpenAILLM(LLMClient):
    """OpenAI-compatible Chat Completions (OpenAI itself, or OpenRouter via `base_url`)
    with JSON mode + Pydantic validation and repair."""

    provider = "openai"

    def __init__(self, tracker: CostTracker, max_validation_retries: int = 2, *, api_key: str | None = None,
                 base_url: str | None = None, label: str = "OpenAI", key_var: str = "OPENAI_API_KEY",
                 token_param: str = "max_completion_tokens", default_headers: dict[str, str] | None = None,
                 fallback_models: list[str] | None = None, max_retries: int = 4):
        super().__init__(tracker, max_validation_retries)
        import openai

        self.label, self.key_var, self.token_param = label, key_var, token_param
        self.fallback_models = list(fallback_models or [])
        self._unavailable: dict[str, str] = {}      # model -> reason; skipped for the rest of this run
        try:
            self.client = openai.OpenAI(max_retries=max_retries, api_key=api_key, base_url=base_url,
                                        default_headers=default_headers)
        except openai.OpenAIError as exc:
            raise ConfigError(f"Set {key_var} in .env to use {label}.") from exc

    def _record(self, agent: str, resp) -> None:
        usage = getattr(resp, "usage", None)
        if usage:
            self.tracker.add(agent, resp.model, usage.prompt_tokens or 0, usage.completion_tokens or 0)

    def _create(self, model: str, **kwargs):
        """Try `model`, then each fallback model, when a model is busy or unavailable.

        Account-level problems (daily free cap, no credits, bad key) raise LLMError at once:
        switching models can't fix those."""
        candidates = [m for m in dict.fromkeys([model, *self.fallback_models]) if m not in self._unavailable]
        if not candidates:
            raise LLMError(self._all_unavailable_message())
        for i, candidate in enumerate(candidates):
            try:
                return self._create_one(candidate, **dict(kwargs))
            except ModelUnavailable as exc:
                self._unavailable[candidate] = exc.reason
                nxt = candidates[i + 1] if i + 1 < len(candidates) else None
                self.notify(f"{candidate} unavailable ({exc.reason})" +
                            (f"; switching to {nxt}" if nxt else ""))
        raise LLMError(self._all_unavailable_message())

    def _all_unavailable_message(self) -> str:
        tried = "; ".join(f"{m}: {r}" for m, r in self._unavailable.items())
        return (f"Every {self.label} model is busy or unavailable right now ({tried}). Free models are often "
                "rate-limited by their providers at busy times; wait a few minutes and use Resume, or add "
                "other models to the fallback list in .env.")

    def _create_one(self, model: str, **kwargs):
        import openai

        max_tokens = kwargs.pop("max_tokens")
        kwargs[self.token_param] = max_tokens
        try:
            resp = self.client.chat.completions.create(model=model, **kwargs)
        except openai.RateLimitError as exc:
            text = str(exc).lower()
            if "free-models-per-day" in text or ("free model" in text and "per day" in text):
                raise LLMError(
                    f"{self.label} daily limit for free models reached. It resets tomorrow (UTC). Adding a small "
                    "credit balance on openrouter.ai raises the free-model limit, or switch LLM_PROVIDER in .env."
                ) from exc
            if "credit" in text or "insufficient_quota" in text or "billing" in text:
                raise LLMError(
                    f"Your {self.label} account has no credits left for this model. Add credits on the "
                    f"{self.label} billing page, use a free model, or switch LLM_PROVIDER in .env "
                    "and restart the backend."
                ) from exc
            raise ModelUnavailable(f"rate-limited: {upstream_reason(exc)}") from exc
        except openai.AuthenticationError as exc:
            raise LLMError(f"{self.label} rejected the API key. Check {self.key_var} in .env.") from exc
        except openai.NotFoundError as exc:
            raise ModelUnavailable(f"not available to this key: {upstream_reason(exc)}") from exc
        except (openai.APITimeoutError, openai.APIConnectionError) as exc:
            raise ModelUnavailable(f"no response: {type(exc).__name__}") from exc
        except openai.APIStatusError as exc:
            if exc.status_code == 402:
                raise ModelUnavailable("needs credits (402)") from exc
            if exc.status_code >= 500 or exc.status_code in (408, 503):
                raise ModelUnavailable(f"provider error {exc.status_code}: {upstream_reason(exc)}") from exc
            raise
        if not getattr(resp, "choices", None):
            # OpenRouter can return HTTP 200 with an error body when the upstream provider fails.
            error = getattr(resp, "error", None) or (getattr(resp, "model_extra", None) or {}).get("error")
            raise ModelUnavailable(f"empty response from provider: {str(error)[:160]}")
        return resp

    def _structured_once(self, *, agent, system, user, schema, model, effort, max_tokens):
        schema_json = json.dumps(schema.model_json_schema())
        system_full = (
            f"{system}\n\nRespond with ONLY a single JSON object (no prose, no code fences) "
            f"that validates against this JSON Schema:\n{schema_json}"
        )
        resp = self._create(
            model,
            messages=[{"role": "system", "content": system_full}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
        self._record(agent, resp)
        choice = resp.choices[0]
        if getattr(choice.message, "refusal", None):
            raise LLMError(f"[{agent}] the model declined: {choice.message.refusal}")
        content = choice.message.content or ""
        if choice.finish_reason == "length":
            raise OutputValidationError("Output was cut off at the token limit. Be more concise.")
        try:
            return schema.model_validate_json(content)
        except ValidationError as exc:
            raise OutputValidationError(summarize_validation_error(exc)) from exc

    def _text_once(self, *, agent, system, user, model, effort, max_tokens):
        resp = self._create(
            model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
        )
        self._record(agent, resp)
        choice = resp.choices[0]
        return TextResult(text=choice.message.content or "", truncated=choice.finish_reason == "length")


def build_llm(settings: Settings, tracker: CostTracker) -> LLMClient:
    if settings.provider == "gemini":
        return GeminiLLM(tracker, max_validation_retries=settings.max_validation_retries)
    if settings.provider == "openai":
        return OpenAILLM(tracker, max_validation_retries=settings.max_validation_retries)
    if settings.provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise ConfigError("Set OPENROUTER_API_KEY in .env to use LLM_PROVIDER=openrouter.")
        return OpenAILLM(tracker, max_validation_retries=settings.max_validation_retries, api_key=key,
                         base_url=OPENROUTER_BASE_URL, label="OpenRouter", key_var="OPENROUTER_API_KEY",
                         token_param="max_tokens", default_headers={"X-Title": "AI Opportunity Pipeline"},
                         fallback_models=settings.fallback_models, max_retries=2)
    raise ConfigError(f"Unknown provider {settings.provider!r}")
