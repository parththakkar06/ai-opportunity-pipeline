"""Settings loaded from .env (and the real environment, which wins)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "outputs"

load_dotenv(PROJECT_ROOT / ".env", override=False)

# An empty `GEMINI_API_KEY=` line in .env would look like a set-but-blank key,
# so drop empty credential variables and let the SDKs report "missing key" clearly.
for _var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
    if os.environ.get(_var, None) is not None and not os.environ[_var].strip():
        del os.environ[_var]

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
VALID_PROVIDERS = {"gemini", "openai", "openrouter"}
DEFAULT_OPENROUTER_MODEL = "google/gemma-4-31b-it:free"
DEFAULT_OPENROUTER_FALLBACKS = "google/gemma-4-31b-it:free,openrouter/free"
DEFAULT_OPENROUTER_CHEAP_MODEL = "google/gemma-4-31b-it:free"
# Mapped to Gemini thinking levels in utils/llm.py (max -> XHIGH).
VALID_EFFORTS = {"minimal", "low", "medium", "high", "xhigh", "max"}


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on", "default"}


@dataclass(frozen=True)
class RubricWeights:
    roi_potential: float = 0.30
    ceo_relevance: float = 0.25
    feasibility: float = 0.20
    speed_to_value: float = 0.15
    competitive_moat: float = 0.10

    FIELDS = ("roi_potential", "ceo_relevance", "feasibility", "speed_to_value", "competitive_moat")

    def normalized(self) -> "RubricWeights":
        total = sum(getattr(self, f) for f in self.FIELDS)
        if total <= 0:
            raise ConfigError("Rubric weights must sum to a positive number")
        return RubricWeights(**{f: getattr(self, f) / total for f in self.FIELDS})

    def as_dict(self) -> dict[str, float]:
        """Normalized weights (they sum to 1), as stored with each strategy."""
        n = self.normalized()
        return {f: round(getattr(n, f), 4) for f in self.FIELDS}


@dataclass
class Settings:
    provider: str = "gemini"
    model: str = DEFAULT_GEMINI_MODEL
    builder_model: str = DEFAULT_GEMINI_MODEL
    effort: str = "medium"
    builder_effort: str = "high"
    build_prototype: bool = True
    fallback_models: list[str] = field(default_factory=list)
    # Phase 1 research budget
    cheap_model: str = DEFAULT_GEMINI_MODEL          # fact extraction (and later: verifier, eval judge)
    max_docs: int = 6                                # full pages/PDFs read per run
    research_time_budget_s: float = 120.0            # search + fetch + gap round
    run_time_budget_s: float = 600.0                 # whole run; past it, optional work (the prototype) is skipped
    gap_round: bool = True
    refresh_cache: bool = False
    tavily_api_key: str | None = None
    serper_api_key: str | None = None
    search_results_per_query: int = 5
    max_validation_retries: int = 2
    weights: RubricWeights = field(default_factory=RubricWeights)
    outputs_dir: Path = DEFAULT_OUTPUTS_DIR


def load_settings(provider_override: str | None = None) -> Settings:
    provider = (provider_override or _env("LLM_PROVIDER", "gemini")).lower()
    if provider == "anthropic":
        raise ConfigError("Anthropic support was replaced by Gemini. Set LLM_PROVIDER=gemini and GEMINI_API_KEY in .env.")
    if provider not in VALID_PROVIDERS:
        raise ConfigError(f"LLM_PROVIDER must be one of {sorted(VALID_PROVIDERS)}, got {provider!r}")

    fallbacks: list[str] = []
    if provider == "gemini":
        model = _env("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        builder_model = _env("GEMINI_BUILDER_MODEL", model)
        cheap_model = _env("GEMINI_CHEAP_MODEL", builder_model)
    elif provider == "openrouter":
        model = _env("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
        builder_model = _env("OPENROUTER_BUILDER_MODEL", model)
        cheap_model = _env("OPENROUTER_CHEAP_MODEL", DEFAULT_OPENROUTER_CHEAP_MODEL)
        fallbacks = [m.strip() for m in _env("OPENROUTER_FALLBACK_MODELS", DEFAULT_OPENROUTER_FALLBACKS).split(",")
                     if m.strip() and m.strip() not in (model, builder_model)]
    else:
        model = _env("OPENAI_MODEL")
        if not model:
            raise ConfigError("LLM_PROVIDER=openai requires OPENAI_MODEL in .env (e.g. the model name you have access to).")
        builder_model = _env("OPENAI_BUILDER_MODEL", model)
        cheap_model = _env("OPENAI_CHEAP_MODEL", model)

    effort = _env("LLM_EFFORT", "medium").lower()
    builder_effort = _env("BUILDER_EFFORT", "high").lower()
    for name, value in (("LLM_EFFORT", effort), ("BUILDER_EFFORT", builder_effort)):
        if value not in VALID_EFFORTS:
            raise ConfigError(f"{name} must be one of {sorted(VALID_EFFORTS)}, got {value!r}")

    weights = RubricWeights(
        roi_potential=_float("WEIGHT_ROI", 0.30),
        ceo_relevance=_float("WEIGHT_CEO_RELEVANCE", 0.25),
        feasibility=_float("WEIGHT_FEASIBILITY", 0.20),
        speed_to_value=_float("WEIGHT_SPEED", 0.15),
        competitive_moat=_float("WEIGHT_MOAT", 0.10),
    ).normalized()

    outputs_dir = Path(_env("OUTPUTS_DIR", str(DEFAULT_OUTPUTS_DIR))).expanduser()

    return Settings(
        provider=provider,
        model=model,
        builder_model=builder_model,
        effort=effort,
        builder_effort=builder_effort,
        build_prototype=_bool("BUILD_PROTOTYPE", True),
        fallback_models=fallbacks,
        cheap_model=_env("CHEAP_MODEL", cheap_model),
        max_docs=max(0, int(_float("MAX_DOCS", 6))),
        research_time_budget_s=_float("RESEARCH_TIME_BUDGET_S", 120.0),
        run_time_budget_s=_float("RUN_TIME_BUDGET_S", 600.0),
        gap_round=_bool("GAP_ROUND", True),
        tavily_api_key=_env("TAVILY_API_KEY"),
        serper_api_key=_env("SERPER_API_KEY"),
        search_results_per_query=int(_float("SEARCH_RESULTS_PER_QUERY", 5)),
        max_validation_retries=int(_float("MAX_VALIDATION_RETRIES", 2)),
        weights=weights,
        outputs_dir=outputs_dir,
    )


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise ConfigError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()
