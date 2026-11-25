"""Offline end-to-end tests: real pipeline code, fake LLM / fake google-genai client and fake web.
Free and fast; no API key needed.

    pytest -q tests/test_pipeline.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from rich.console import Console

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.base import (  # noqa: E402
    CHALLENGES_JSON, META_JSON, OPPORTUNITIES_JSON, PITCH_JSON, PITCH_MD, PROFILE_JSON, PROTOTYPE_HTML,
    REPORT_JSON, REPORT_MD, STRATEGY_JSON, STRATEGY_MD,
)
from agents.builder import compute_roi, finalize_prototype_html  # noqa: E402
from agents.evaluator import rank_opportunities, weighted_score  # noqa: E402
from run_pipeline import PipelineError, run_pipeline  # noqa: E402
from utils.config import RubricWeights, Settings  # noqa: E402
from utils.console import PipelineUI  # noqa: E402
from utils.costs import CostTracker  # noqa: E402
from utils.io import slugify  # noqa: E402
from google.genai import errors as genai_errors, types as genai_types  # noqa: E402
from utils.llm import GeminiLLM, LLMClient, LLMError, OutputValidationError, TextResult  # noqa: E402
from utils.schemas import (  # noqa: E402
    AIOpportunities, BusinessProfile, EvaluationScores, ExecutivePitchDraft, WinningStrategy,
)
from utils.search import (  # noqa: E402
    HomepageSignals, Query, SearchResult, WebResearch, guess_official_website, parse_homepage,
)

FIXTURES = ROOT / "tests" / "fixtures"
BUSINESS = "Maple Street Dental"
MODEL = "gemini-3.8-flash"


@pytest.fixture(autouse=True)
def _test_prices(monkeypatch):
    """No Gemini prices are hard-coded, so give the tests a price to exercise cost tracking."""
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


# --------------------------------------------------------------------------- fakes
class FakeLLM(LLMClient):
    """Returns fixture data per schema. `bad_first` makes the first call for a schema return invalid
    data so we can prove the repair loop works. `forbid` raises if a schema is requested."""

    provider = "fake"

    def __init__(self, bad_first: set[str] | None = None, forbid: set[str] | None = None):
        super().__init__(CostTracker(), max_validation_retries=2)
        self.calls: list[str] = []
        self.bad_first = set(bad_first or ())
        self.forbid = set(forbid or ())
        self.prompts: dict[str, str] = {}

    def _structured_once(self, *, agent, system, user, schema, model, effort, max_tokens):
        name = schema.__name__
        if name in self.forbid:
            raise AssertionError(f"{name} should not have been requested")
        self.calls.append(name)
        self.prompts[name] = user
        self.tracker.add(agent, MODEL, 1000, 500)
        data = json.loads((FIXTURES / f"{name}.json").read_text())
        if name in self.bad_first:
            self.bad_first.discard(name)
            if name == "AIOpportunities":
                data["opportunities"] = data["opportunities"][:2]   # valid schema, fails the 5-7 check
            else:
                raise OutputValidationError("- scores: field required")
        return schema.model_validate(data)

    def _text_once(self, *, agent, system, user, model, effort, max_tokens):
        self.calls.append("prototype")
        self.tracker.add(agent, MODEL, 2000, 4000)
        return TextResult((FIXTURES / "prototype.html").read_text(), truncated=False)


class FakeProvider:
    def __init__(self, name: str, results: int = 3, fail: bool = False):
        self.name, self.n, self.fail = name, results, fail
        self.queries: list[str] = []

    def search(self, query, max_results, topic):
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("rate limited")
        return [
            SearchResult(title=f"{query} #{i}", url=f"https://example.com/{abs(hash(query))}/{i}",
                         snippet="Maple Street Dental offers family dentistry.", provider=self.name, query=query)
            for i in range(self.n)
        ]


INVESTOR_URLS = [
    "https://maplestreetdental.example/investors/q2-2026-update.pdf",
    "https://maplestreetdental.example/press/round-rock-opening",
]


class FakeResearch(WebResearch):
    """Search returns generic results plus two pages on the company's own investor/press domain, which
    rank as primary sources; fetch_document serves a fixture document for any URL."""

    def __init__(self, providers=None, with_documents: bool = True):
        super().__init__(providers or [FakeProvider("tavily")], results_per_query=3)
        self.fetched: list[str] = []
        self.documents_fetched: list[str] = []
        self.with_documents = with_documents

    def search_many(self, queries, cache=None):
        bundle = super().search_many(queries, cache=cache)
        if self.with_documents:
            seen = {r.url for r in bundle.results}
            for url in INVESTOR_URLS:
                if url not in seen:
                    bundle.results.insert(0, SearchResult(title="Maple Street Dental investor update", url=url,
                                                          snippet="Q2 2026 update", provider="tavily", query="fixture"))
        return bundle

    def fetch_document(self, url, timeout=12.0):
        from datetime import date as _date
        from utils.fetch import FetchedDoc
        self.documents_fetched.append(url)
        return FetchedDoc(url=url, title="Maple Street Dental investor update",
                          text=(FIXTURES / "investor_update.txt").read_text(),
                          kind="pdf" if url.endswith(".pdf") else "html", published=None,
                          retrieved=_date.today().isoformat(), via="httpx")

    def fetch_homepage(self, url):
        self.fetched.append(url)
        return HomepageSignals(url=url, title="Maple Street Dental", theme_color="#0F766E",
                               tech_signals=["WordPress"], text_excerpt="Gentle care for every smile")


def quiet_ui() -> PipelineUI:
    return PipelineUI(Console(file=io.StringIO(), width=120))


def settings(tmp_path: Path) -> Settings:
    return Settings(outputs_dir=tmp_path)


# --------------------------------------------------------------------------- end-to-end
def test_full_pipeline_offline(tmp_path):
    llm, research = FakeLLM(), FakeResearch()
    result = run_pipeline(BUSINESS, url="maplestreetdental.example", settings=settings(tmp_path),
                          llm=llm, research=research, ui=quiet_ui())

    out = tmp_path / "maple-street-dental"
    assert result.out_dir == out
    for name in (PROFILE_JSON, CHALLENGES_JSON, OPPORTUNITIES_JSON, STRATEGY_JSON, STRATEGY_MD,
                 PITCH_MD, PITCH_JSON, PROTOTYPE_HTML, META_JSON, REPORT_JSON, REPORT_MD):
        assert (out / name).exists(), f"missing {name}"

    # Every JSON handoff validates against its schema.
    BusinessProfile.model_validate_json((out / PROFILE_JSON).read_text())
    assert len(AIOpportunities.model_validate_json((out / OPPORTUNITIES_JSON).read_text()).opportunities) == 5
    strategy = WinningStrategy.model_validate_json((out / STRATEGY_JSON).read_text())

    # Python, not the LLM, picks the winner: opp-1 = 83.5 raw, 78.1 once ROI 9 is shrunk to 7.2
    # (evidence share 0.5: one public-data driver, one benchmark, one assumption).
    assert strategy.winner.id == "opp-1"
    assert strategy.winner_weighted_score == pytest.approx(78.1)
    assert [r.opportunity_id for r in strategy.ranking] == ["opp-1", "opp-5", "opp-3", "opp-2", "opp-4"]

    md = (out / STRATEGY_MD).read_text()
    assert "Winning AI Strategy" in md and "| 1 | No-show prediction" in md

    pitch = (out / PITCH_MD).read_text()
    for section in ("Cold outreach email", "60-second elevator pitch", "ROI breakdown", "**Subject:**"):
        assert section in pitch
    assert "$55,000" in pitch  # 50,000 + 5,000 conservative annual value

    html = (out / PROTOTYPE_HTML).read_text()
    assert html.startswith("<!DOCTYPE html>") and html.rstrip().endswith("</html>")
    assert "cdn.tailwindcss.com" in html and "```" not in html
    assert "addEventListener" in html

    # --url reached the researcher: used for queries and the homepage fetch.
    assert research.fetched == ["https://maplestreetdental.example"]
    assert any("site:maplestreetdental.example" in q for q in research.providers[0].queries)
    assert "maplestreetdental.example" in llm.prompts["BusinessProfileDraft"]

    meta = json.loads((out / META_JSON).read_text())
    assert meta["total_input_tokens"] > 0 and meta["total_cost_usd"] > 0
    assert meta["search_providers_used"] == ["tavily"]


def test_resume_from_stage_3_reuses_saved_outputs(tmp_path):
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui())
    llm = FakeLLM(forbid={"BusinessProfile", "BusinessChallenges"})
    run_pipeline(BUSINESS, from_step=3, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=quiet_ui())
    assert llm.calls == ["AIOpportunities", "EvaluationScores", "ExecutiveSummary", "ExecutivePitchDraft",
                         "ClaimVerdicts", "prototype"]


def test_resume_from_stage_4_only_rebuilds_the_pitch(tmp_path):
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui())
    llm = FakeLLM(forbid={"BusinessProfile", "BusinessChallenges", "AIOpportunities", "EvaluationScores"})
    run_pipeline(BUSINESS, from_step=4, settings=settings(tmp_path), llm=llm, research=FakeResearch(),
                 ui=quiet_ui(), build_prototype=False)
    assert llm.calls == ["ExecutivePitchDraft", "ClaimVerdicts"]   # pitch + one verifier check


def test_resume_without_inputs_fails_clearly(tmp_path):
    with pytest.raises(PipelineError, match="missing 01_business_profile.json"):
        run_pipeline(BUSINESS, from_step=2, settings=settings(tmp_path), llm=FakeLLM(),
                     research=FakeResearch(), ui=quiet_ui())


def test_invalid_output_is_repaired(tmp_path):
    llm = FakeLLM(bad_first={"AIOpportunities", "EvaluationScores"})
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=quiet_ui())
    assert llm.calls.count("AIOpportunities") == 2
    assert llm.calls.count("EvaluationScores") == 2
    # The retry prompt carried the validation feedback.
    assert "previous_attempt_feedback" in llm.prompts["AIOpportunities"]


def test_gives_up_after_max_retries():
    class AlwaysBad(FakeLLM):
        def _structured_once(self, **kw):
            raise OutputValidationError("- business_name: field required")

    with pytest.raises(LLMError, match="after 3 attempts"):
        AlwaysBad().structured(agent="t", system="s", user="u", schema=BusinessProfile,
                               model="m", effort="low")


def test_thin_search_results_force_low_data_quality(tmp_path):
    class NoHomepage(FakeResearch):
        def fetch_homepage(self, url):
            return None

    research = NoHomepage([FakeProvider("duckduckgo", results=0)], with_documents=False)
    run_pipeline("Tiny Bakery", settings=settings(tmp_path), llm=FakeLLM(), research=research, ui=quiet_ui())
    profile = BusinessProfile.model_validate_json((tmp_path / "tiny-bakery" / PROFILE_JSON).read_text())
    assert profile.data_quality == "low"


# --------------------------------------------------------------------------- units
def test_search_falls_back_to_next_provider():
    broken, backup = FakeProvider("tavily", fail=True), FakeProvider("duckduckgo")
    bundle = WebResearch([broken, backup]).search_many([Query("Maple Street Dental")])
    assert bundle.providers_used == ["duckduckgo"]
    assert len(bundle.results) == 3
    assert bundle.errors and "tavily failed" in bundle.errors[0]


def test_weighted_score_and_custom_weights():
    scores = EvaluationScores.model_validate_json((FIXTURES / "EvaluationScores.json").read_text())
    opps = AIOpportunities.model_validate_json((FIXTURES / "AIOpportunities.json").read_text())
    assert weighted_score(scores.scores[0], RubricWeights()) == pytest.approx(83.5)
    # Weight speed only: opp-5 (speed 9) must beat opp-1 (speed 8).
    speed_only = RubricWeights(roi_potential=0, ceo_relevance=0, feasibility=0, speed_to_value=1, competitive_moat=0)
    assert rank_opportunities(opps, scores, speed_only)[0].opportunity_id == "opp-5"


def test_out_of_range_scores_are_clamped():
    scores = EvaluationScores.model_validate_json((FIXTURES / "EvaluationScores.json").read_text())
    scores.scores[3].roi_potential.score = 42
    opps = AIOpportunities.model_validate_json((FIXTURES / "AIOpportunities.json").read_text())
    ranked = rank_opportunities(opps, scores, RubricWeights())
    assert all(1 <= r.scores.roi_potential.score <= 10 for r in ranked)


def test_roi_math():
    draft = ExecutivePitchDraft.model_validate_json((FIXTURES / "ExecutivePitchDraft.json").read_text())
    roi = compute_roi(draft)
    assert roi.annual_value_usd_low == 55000 and roi.annual_value_usd_high == 72500
    assert roi.net_annual_value_usd_low == 49000
    assert roi.payback_months_worst == pytest.approx(round(25000 / (49000 / 12), 1))
    assert roi.three_year_roi_pct_low == pytest.approx(round((3 * 49000 - 25000) / 25000 * 100))


def test_roi_with_no_net_value_has_no_payback():
    draft = ExecutivePitchDraft.model_validate_json((FIXTURES / "ExecutivePitchDraft.json").read_text())
    draft.annual_running_cost_usd = 1_000_000
    assert compute_roi(draft).payback_months_worst is None


def test_prototype_sanitizer_handles_fragments_and_truncation():
    html, notes = finalize_prototype_html("<div>hi</div>", "Demo")
    assert html.startswith("<!DOCTYPE html>") and "cdn.tailwindcss.com" in html and html.rstrip().endswith("</html>")
    assert notes
    truncated, notes = finalize_prototype_html("<!DOCTYPE html><html><head></head><body><div>cut", "Demo")
    assert truncated.rstrip().endswith("</html>") and any("truncated" in n for n in notes)


def test_homepage_parsing_detects_tech():
    page = ('<html><head><title>Acme</title><meta name="theme-color" content="#123456">'
            '<script src="https://cdn.shopify.com/x.js"></script></head><body><h1>Hello</h1></body></html>')
    signals = parse_homepage("https://acme.example", page)
    assert signals.title == "Acme" and signals.theme_color == "#123456"
    assert "Shopify" in signals.tech_signals and signals.headings == ["Hello"]


def test_guess_official_website_skips_directories():
    results = [
        SearchResult("Yelp", "https://www.yelp.com/biz/maple-street-dental", "", "x", "q"),
        SearchResult("Home", "https://www.maplestreetdental.com/about", "", "x", "q"),
    ]
    assert guess_official_website(BUSINESS, results) == "https://maplestreetdental.com"


def test_slugify():
    assert slugify("Café Olé & Co.") == "cafe-ole-co"
    assert slugify("   ") == "business"


# --------------------------------------------------------------------------- google-genai client mocks
def genai_response(text: str, finish: str = "STOP", prompt_tokens: int = 100, out_tokens: int = 50,
                   thoughts: int = 20, block_reason: str | None = None) -> genai_types.GenerateContentResponse:
    """A real google-genai response object, built offline."""
    feedback = genai_types.GenerateContentResponsePromptFeedback(block_reason=block_reason) if block_reason else None
    candidates = [] if block_reason else [genai_types.Candidate(
        content=genai_types.Content(role="model", parts=[genai_types.Part(text=text)]),
        finish_reason=finish,
    )]
    return genai_types.GenerateContentResponse(
        candidates=candidates,
        prompt_feedback=feedback,
        usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt_tokens, candidates_token_count=out_tokens, thoughts_token_count=thoughts),
    )


class FakeGenaiModels:
    """Stands in for `genai.Client().models`. Answers from fixtures based on `config.response_schema`."""

    def __init__(self, scripted: list | None = None, reject_thinking: bool = False):
        self.scripted = list(scripted or [])      # responses/exceptions returned before fixture answers
        self.reject_thinking = reject_thinking
        self.configs: list[genai_types.GenerateContentConfig] = []
        self.contents: list[str] = []

    def _maybe_reject(self, config):
        if self.reject_thinking and config.thinking_config is not None:
            raise genai_errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT",
                                                           "message": "thinking_level is not supported for this model."}})

    def generate_content(self, *, model, contents, config):
        self.configs.append(config)
        self.contents.append(contents)
        self._maybe_reject(config)
        if self.scripted:
            item = self.scripted.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        name = config.response_schema.__name__
        return genai_response((FIXTURES / f"{name}.json").read_text())

    def generate_content_stream(self, *, model, contents, config):
        self.configs.append(config)
        self._maybe_reject(config)
        html = (FIXTURES / "prototype.html").read_text()
        third = len(html) // 3
        chunks = [html[:third], html[third:2 * third], html[2 * third:]]
        for i, piece in enumerate(chunks):
            last = i == len(chunks) - 1
            yield genai_types.GenerateContentResponse(
                candidates=[genai_types.Candidate(
                    content=genai_types.Content(role="model", parts=[genai_types.Part(text=piece)]),
                    finish_reason="STOP" if last else None)],
                usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=500, candidates_token_count=3000, thoughts_token_count=200) if last else None,
            )


class FakeGenaiClient:
    def __init__(self, **kwargs):
        self.models = FakeGenaiModels(**kwargs)


def gemini(client: FakeGenaiClient) -> GeminiLLM:
    return GeminiLLM(CostTracker(), max_validation_retries=2, client=client)


def test_full_pipeline_through_gemini_client(tmp_path):
    client = FakeGenaiClient()
    llm = gemini(client)
    run_pipeline(BUSINESS, url="maplestreetdental.example", settings=settings(tmp_path), llm=llm,
                 research=FakeResearch(), ui=quiet_ui())
    out = tmp_path / "maple-street-dental"
    strategy = WinningStrategy.model_validate_json((out / STRATEGY_JSON).read_text())
    assert strategy.winner.id == "opp-1"
    assert (out / PROTOTYPE_HTML).read_text().rstrip().endswith("</html>")

    structured = [c for c in client.models.configs if c.response_schema is not None]
    assert [c.response_schema.__name__ for c in structured] == [
        "FactBatch", "FactBatch", "BusinessProfileDraft",            # stage 1: extraction, profile
        "FactBatch", "BusinessProfileDraft",                          # stage 1: one gap-filling round
        "BusinessChallenges", "AIOpportunities", "EvaluationScores", "ExecutiveSummary", "ExecutivePitchDraft",
        "ClaimVerdicts"]                                              # stage 4: one verifier call for leftovers
    for c in client.models.configs:
        assert c.system_instruction and isinstance(c.system_instruction, str)
        assert c.thinking_config is not None
    for c in structured:
        assert c.response_mime_type == "application/json"
    # Effort maps to thinking levels: challenge analysis, scoring and the prototype run at BUILDER_EFFORT=high.
    levels = [getattr(c.thinking_config.thinking_level, "name", c.thinking_config.thinking_level)
              for c in client.models.configs]
    # Fact extraction runs on the cheap model at low effort.
    assert levels == ["LOW", "LOW", "MEDIUM", "LOW", "MEDIUM", "HIGH", "MEDIUM", "HIGH", "MEDIUM", "MEDIUM", "LOW", "HIGH"]

    meta = json.loads((out / META_JSON).read_text())
    # 11 structured calls x (100 in, 50+20 out) + stream (500 in, 3000+200 out); thinking counts as output.
    assert meta["total_input_tokens"] == 11 * 100 + 500
    assert meta["total_output_tokens"] == 11 * 70 + 3200
    # Tokens are logged per stage and add up to the total.
    assert meta["stages"]["1"]["calls"] == 5
    assert sum(st["input_tokens"] for st in meta["stages"].values()) == meta["total_input_tokens"]


def test_gemini_parses_into_pydantic_and_records_usage():
    llm = gemini(FakeGenaiClient())
    profile = llm.structured(agent="researcher", system="sys", user="u", schema=BusinessProfile,
                             model=MODEL, effort="low")
    assert isinstance(profile, BusinessProfile) and profile.business_name == BUSINESS
    totals = llm.tracker.for_agent("researcher")
    assert (totals.input_tokens, totals.output_tokens) == (100, 70)
    assert totals.cost_usd == pytest.approx((100 * 1.0 + 70 * 2.0) / 1_000_000)


def test_gemini_repairs_malformed_json():
    client = FakeGenaiClient(scripted=[genai_response('{"business_name": "Maple"')])  # truncated JSON
    llm = gemini(client)
    llm.structured(agent="t", system="s", user="u", schema=BusinessProfile, model=MODEL, effort="low")
    assert len(client.models.contents) == 2
    assert "previous_attempt_feedback" in client.models.contents[1]


def test_gemini_max_tokens_triggers_repair():
    client = FakeGenaiClient(scripted=[genai_response("{}", finish="MAX_TOKENS")])
    gemini(client).structured(agent="t", system="s", user="u", schema=BusinessProfile, model=MODEL, effort="low")
    assert "cut off" in client.models.contents[1]


def test_gemini_safety_block_is_not_retried():
    client = FakeGenaiClient(scripted=[genai_response("", block_reason="SAFETY")])
    with pytest.raises(LLMError, match="blocked the prompt"):
        gemini(client).structured(agent="t", system="s", user="u", schema=BusinessProfile, model=MODEL, effort="low")
    assert len(client.models.contents) == 1


def test_gemini_drops_thinking_level_if_model_rejects_it():
    client = FakeGenaiClient(reject_thinking=True)
    llm = gemini(client)
    llm.structured(agent="t", system="s", user="u", schema=BusinessProfile, model=MODEL, effort="high")
    assert client.models.configs[0].thinking_config is not None
    assert client.models.configs[-1].thinking_config is None
    assert llm.use_thinking_level is False


def test_gemini_retries_transient_server_errors(monkeypatch):
    monkeypatch.setattr(GeminiLLM._structured_once.retry, "sleep", lambda _s: None)  # no real backoff wait
    busy = genai_errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "overloaded"}})
    client = FakeGenaiClient(scripted=[busy])
    gemini(client).structured(agent="t", system="s", user="u", schema=BusinessProfile, model=MODEL, effort="low")
    assert len(client.models.contents) == 2


def test_gemini_text_streams_and_joins_chunks():
    llm = gemini(FakeGenaiClient())
    result = llm.text(agent="builder", system="s", user="u", model=MODEL, effort="high")
    assert result.text == (FIXTURES / "prototype.html").read_text()
    assert result.truncated is False
    assert llm.tracker.for_agent("builder").output_tokens == 3200


def test_gemini_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    from utils.config import ConfigError
    with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
        GeminiLLM(CostTracker())


def test_gemini_real_client_builds_with_key(monkeypatch):
    """Constructs the real SDK client (no network call) to check our retry/http options are valid."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    llm = GeminiLLM(CostTracker())
    assert llm.client.models is not None


def test_settings_reject_removed_anthropic_provider():
    from utils.config import ConfigError, load_settings
    with pytest.raises(ConfigError, match="replaced by Gemini"):
        load_settings("anthropic")
    s = load_settings("gemini")
    assert s.provider == "gemini" and s.model


# --------------------------------------------------------------------------- quota handling
DAILY_QUOTA_BODY = {"error": {
    "code": 429, "status": "RESOURCE_EXHAUSTED",
    "message": ("You exceeded your current quota, please check your plan and billing details. \n* Quota exceeded "
                "for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, "
                "model: gemini-3.8-flash, description: Generate content requests per day limit exceeded on Free "
                "Tier.\nPlease retry in 20h59m1.354420194s."),
    "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{
            "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
            "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
            "quotaDimensions": {"model": "gemini-3.8-flash", "location": "global"}, "quotaValue": "20"}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "75541s"},
    ],
}}


def test_daily_quota_fails_fast_with_clear_message(monkeypatch):
    monkeypatch.setattr(GeminiLLM._structured_once.retry, "sleep", lambda _s: None)
    client = FakeGenaiClient(scripted=[genai_errors.ClientError(429, DAILY_QUOTA_BODY)])
    with pytest.raises(LLMError) as info:
        gemini(client).structured(agent="t", system="s", user="u", schema=BusinessProfile, model=MODEL, effort="low")
    message = str(info.value)
    assert len(client.models.contents) == 1, "a daily quota must not be retried"
    assert "free-tier daily quota reached for gemini-3.8-flash (20 requests per day)" in message
    assert "resets in about 20h 59m" in message
    assert "GEMINI_MODEL" in message and "{'error'" not in message


def test_short_rate_limit_is_still_retried(monkeypatch):
    monkeypatch.setattr(GeminiLLM._structured_once.retry, "sleep", lambda _s: None)
    per_minute = genai_errors.ClientError(429, {"error": {
        "code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Rate limit per minute exceeded.",
        "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "12s"}]}})
    client = FakeGenaiClient(scripted=[per_minute])
    gemini(client).structured(agent="t", system="s", user="u", schema=BusinessProfile, model=MODEL, effort="low")
    assert len(client.models.contents) == 2


def test_sdk_http_retries_skip_429(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    from utils.llm import SDK_RETRY_STATUS
    assert 429 not in SDK_RETRY_STATUS and 503 in SDK_RETRY_STATUS


def test_openai_out_of_credits_gives_clear_message(monkeypatch):
    import httpx
    import openai
    from utils.llm import OpenAILLM

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    llm = OpenAILLM(CostTracker())
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    no_credits = openai.RateLimitError(
        "Error code: 429 - You have no credits remaining. Add credits to continue using the API.",
        response=httpx.Response(429, request=request), body=None)

    def raise_no_credits(**_kw):
        raise no_credits

    monkeypatch.setattr(llm.client.chat.completions, "create", raise_no_credits)
    with pytest.raises(LLMError, match="no credits left"):
        llm.structured(agent="t", system="s", user="u", schema=BusinessProfile, model="gpt-6.2-sol", effort="low")


def test_openrouter_provider_builds_openai_compatible_client(monkeypatch):
    from utils.config import load_settings
    from utils.llm import OPENROUTER_BASE_URL, OpenAILLM, build_llm

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
    s = load_settings("openrouter")
    llm = build_llm(s, CostTracker())
    assert isinstance(llm, OpenAILLM) and s.model == "google/gemma-4-31b-it:free"
    assert str(llm.client.base_url).rstrip("/") == OPENROUTER_BASE_URL
    assert llm.token_param == "max_tokens" and llm.label == "OpenRouter"


def test_openrouter_free_models_cost_nothing():
    from utils.costs import price_for
    assert price_for("baidu/ernie-5.5-flash-preview:free") == (0.0, 0.0)


def test_openrouter_daily_free_limit_message(monkeypatch):
    import httpx
    import openai
    from utils.config import load_settings
    from utils.llm import build_llm

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    llm = build_llm(load_settings("openrouter"), CostTracker())
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    limited = openai.RateLimitError("Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000 free model requests per day",
                                    response=httpx.Response(429, request=request), body=None)

    def raise_limited(**_kw):
        raise limited

    monkeypatch.setattr(llm.client.chat.completions, "create", raise_limited)
    with pytest.raises(LLMError, match="daily limit for free models"):
        llm.structured(agent="t", system="s", user="u", schema=BusinessProfile, model="x:free", effort="low")


# --------------------------------------------------------------------------- OpenRouter model fallback
def _openrouter_llm(monkeypatch, fallbacks=("google/gemma-4-31b-it:free", "openrouter/free")):
    from utils.llm import OPENROUTER_BASE_URL, OpenAILLM
    return OpenAILLM(CostTracker(), api_key="test-key-not-real", base_url=OPENROUTER_BASE_URL, label="OpenRouter",
                     key_var="OPENROUTER_API_KEY", token_param="max_tokens", fallback_models=list(fallbacks),
                     max_retries=0)


def _provider_429():
    import httpx
    import openai
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    body = {"message": "Provider returned error", "code": 429,
            "metadata": {"raw": "baidu/ernie-5.5-flash-preview:free is temporarily rate-limited upstream.",
                         "provider_name": "Baidu"}}
    return openai.RateLimitError("Error code: 429 - Provider returned error",
                                 response=httpx.Response(429, request=request), body=body)


def _ok_completion(model: str, content: str):
    from openai.types.chat import ChatCompletion
    return ChatCompletion.model_validate({
        "id": "x", "object": "chat.completion", "created": 0, "model": model,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    })


def test_openrouter_falls_back_on_provider_rate_limit(monkeypatch):
    llm = _openrouter_llm(monkeypatch)
    notes, called = [], []
    llm.notify = notes.append
    content = (FIXTURES / "EvaluationScores.json").read_text()

    def create(*, model, **_kw):
        called.append(model)
        if model.startswith("baidu/"):
            raise _provider_429()
        return _ok_completion(model, content)

    monkeypatch.setattr(llm.client.chat.completions, "create", create)
    from utils.schemas import EvaluationScores as ES
    out = llm.structured(agent="t", system="s", user="u", schema=ES, model="baidu/ernie-5.5-flash-preview:free",
                         effort="low")
    assert len(out.scores) == 5
    assert called == ["baidu/ernie-5.5-flash-preview:free", "google/gemma-4-31b-it:free"]
    assert "temporarily rate-limited upstream" in notes[0] and "switching to google/gemma-4-31b-it:free" in notes[0]
    assert llm.tracker.records[-1].model == "google/gemma-4-31b-it:free"

    # The busy model is skipped for the rest of the run, so later calls don't waste a request on it.
    called.clear()
    llm.structured(agent="t", system="s", user="u", schema=ES, model="baidu/ernie-5.5-flash-preview:free", effort="low")
    assert called == ["google/gemma-4-31b-it:free"]


def test_openrouter_all_models_busy_gives_clear_error(monkeypatch):
    llm = _openrouter_llm(monkeypatch, fallbacks=("google/gemma-4-31b-it:free",))

    def create(**_kw):
        raise _provider_429()

    monkeypatch.setattr(llm.client.chat.completions, "create", create)
    with pytest.raises(LLMError, match="Every OpenRouter model is busy") as info:
        llm.structured(agent="t", system="s", user="u", schema=BusinessProfile, model="baidu/x:free", effort="low")
    assert "Baidu: " in str(info.value) and "Resume" in str(info.value)


def test_openrouter_daily_cap_does_not_fall_back(monkeypatch):
    import httpx
    import openai
    llm = _openrouter_llm(monkeypatch)
    called = []
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")

    def create(*, model, **_kw):
        called.append(model)
        raise openai.RateLimitError("Rate limit exceeded: free-models-per-day",
                                    response=httpx.Response(429, request=request), body=None)

    monkeypatch.setattr(llm.client.chat.completions, "create", create)
    with pytest.raises(LLMError, match="daily limit for free models"):
        llm.structured(agent="t", system="s", user="u", schema=BusinessProfile, model="baidu/x:free", effort="low")
    assert len(called) == 1, "the daily cap applies to every free model, so switching is pointless"


def test_settings_build_openrouter_fallback_list(monkeypatch):
    from utils.config import load_settings
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODELS", "google/gemma-4-31b-it:free, openrouter/free ,")
    assert load_settings("openrouter").fallback_models == ["openrouter/free"]   # main model not repeated
