"""Offline tests for the 5-section assessment report, the new pipeline checks, the DuckDuckGo
fallback hardening, and the FastAPI backend (including the SSE progress stream). No API keys."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import api.index as api_module  # noqa: E402
from agents.analyst import check_challenges  # noqa: E402
from agents.base import PROFILE_JSON, PROTOTYPE_HTML, REPORT_JSON, REPORT_MD  # noqa: E402
from agents.report import build_report, render_ceo_pitch_text, render_report_markdown  # noqa: E402
from agents.strategist import check_opportunities  # noqa: E402
from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import (  # noqa: E402
    BUSINESS, FIXTURES, FakeLLM, FakeProvider, FakeResearch, quiet_ui, settings,
)
from utils.schemas import AIOpportunities, AssessmentReport, BusinessChallenges  # noqa: E402
from utils.search import DDG_MAX_QUERIES, DuckDuckGoSearch, Query, WebResearch  # noqa: E402

SECTION_HEADINGS = [
    "## 1. Company Overview", "## 2. Key Business Information", "## 3. Potential Business Challenges",
    "## 4. AI Opportunities", "## 5. Personalized CEO Pitch",
]


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


def full_run(tmp_path: Path, **kw) -> Path:
    run_pipeline(BUSINESS, url="maplestreetdental.example", settings=settings(tmp_path), llm=FakeLLM(),
                 research=FakeResearch(), ui=quiet_ui(), **kw)
    return tmp_path / "maple-street-dental"


# --------------------------------------------------------------------------- 5-section report
def test_full_run_writes_all_five_sections(tmp_path):
    out = full_run(tmp_path)
    report = AssessmentReport.model_validate_json((out / REPORT_JSON).read_text())
    assert report.stages_completed == [1, 2, 3, 4]

    ov = report.company_overview
    assert ov.what_they_do and ov.industry == "Healthcare"
    assert ov.scale.projects_or_portfolio == "2 clinics, 14 chairs"
    assert ov.geographic_presence == ["Austin, TX", "Round Rock, TX"]

    kb = report.key_business_information
    assert kb.major_projects[0].name == "Round Rock clinic"
    assert kb.expansion_plans and kb.public_information and kb.recent_developments

    assert {c.category for c in report.business_challenges} == {"operational", "sales", "customer_experience"}
    assert all(len(c.reasoning.split()) >= 20 for c in report.business_challenges)

    opp = report.ai_opportunities
    assert [o.rank for o in opp] == [1, 2, 3, 4, 5]
    assert opp[0].is_recommended and opp[0].id == report.recommended_opportunity_id == "opp-1"
    assert all(o.addresses_challenges and o.applies_to for o in opp)

    pitch = report.ceo_pitch
    assert pitch.addressed_to.startswith("Dr. Priya Patel")
    assert pitch.why_we_reached_out and len(pitch.opportunities_identified) == 3
    assert pitch.recommended_solutions[0].name.startswith("No-show")
    assert pitch.roi_headline and "$55,000" in pitch.roi_headline

    md = (out / REPORT_MD).read_text()
    positions = [md.index(h) for h in SECTION_HEADINGS]
    assert positions == sorted(positions), "sections must appear in order 1-5"
    assert md.count("**Reasoning:**") == len(report.business_challenges)

    text = render_ceo_pitch_text(report)
    assert text.startswith("Filling Maple Street") and "Why we reached out" in text and "[Your Name]" in text


def test_ceo_pitch_markdown_is_one_page_first(tmp_path):
    out = full_run(tmp_path)
    pitch_md = (out / "04_ceo_pitch.md").read_text()
    assert pitch_md.startswith("# Filling Maple Street's empty chairs with AI")
    one_page = pitch_md.split("# Appendix")[0]
    for part in ("**To:** Dr. Priya Patel", "## Why we reached out", "## Opportunities we identified",
                 "## What we recommend"):
        assert part in one_page
    assert len(one_page.split()) < 450


def test_no_prototype_option(tmp_path):
    out = full_run(tmp_path, build_prototype=False)
    assert not (out / PROTOTYPE_HTML).exists()
    assert build_report(out).prototype_available is False


def test_legacy_partial_run_still_builds_a_report(tmp_path):
    run = tmp_path / "old-run"
    run.mkdir()
    shutil.copy(FIXTURES / "legacy_profile.json", run / PROFILE_JSON)
    report = build_report(run)
    assert report.stages_completed == [1]
    assert report.ai_opportunities == [] and report.ceo_pitch is None
    assert len(report.business_challenges) == 3            # derived from the profile's bottlenecks
    assert all(c.reasoning for c in report.business_challenges)
    md = render_report_markdown(report)
    assert all(h in md for h in SECTION_HEADINGS)
    assert "has not run yet" in md


# --------------------------------------------------------------------------- new checks
def test_challenge_check_demands_reasoning_and_coverage():
    good = BusinessChallenges.model_validate_json((FIXTURES / "BusinessChallenges.json").read_text())
    assert check_challenges(good) is None
    thin = good.model_copy(deep=True)
    thin.challenges[0].reasoning = "Reviews say so."
    assert "reasoning is too thin" in check_challenges(thin)
    one_sided = good.model_copy(deep=True)
    for c in one_sided.challenges:
        c.category = "operational"
    assert "customer_experience" in check_challenges(one_sided)


def test_challenge_repair_loop_in_pipeline(tmp_path):
    class ThinFirst(FakeLLM):
        def _structured_once(self, **kw):
            result = super()._structured_once(**kw)
            if kw["schema"] is BusinessChallenges and self.calls.count("BusinessChallenges") == 1:
                result.challenges = result.challenges[:2]
            return result

    llm = ThinFirst()
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    assert llm.calls.count("BusinessChallenges") == 2
    assert "previous_attempt_feedback" in llm.prompts["BusinessChallenges"]


def test_strategist_check_rejects_unmapped_or_unknown_challenges():
    opps = AIOpportunities.model_validate_json((FIXTURES / "AIOpportunities.json").read_text())
    ids = {"ch-1", "ch-2", "ch-3", "ch-4", "ch-5"}
    assert check_opportunities(opps, ids) is None
    opps.opportunities[0].addresses_challenges = ["ch-99"]
    opps.opportunities[1].applies_to = ""
    problem = check_opportunities(opps, ids)
    assert "unknown challenge ids ['ch-99']" in problem and "opp-2 needs applies_to" in problem


# --------------------------------------------------------------------------- DuckDuckGo hardening
def test_failing_provider_is_skipped_after_two_failures():
    broken = FakeProvider("duckduckgo", fail=True)
    bundle = WebResearch([broken]).search_many([Query(f"q{i}") for i in range(5)])
    assert len(broken.queries) == 2                 # circuit breaker: no 3rd, 4th, 5th attempt
    assert any("skipped for the rest of this run" in e for e in bundle.errors)
    assert all("\n" not in e for e in bundle.errors)


def test_keyless_research_uses_fewer_queries_and_tight_timeout():
    from utils.config import Settings
    research = WebResearch.from_settings(Settings())  # no Tavily / Serper keys
    assert research.provider_names == ["duckduckgo"]
    assert research.max_queries == DDG_MAX_QUERIES
    assert research.providers[0].timeout <= 10
    probe = FakeProvider("duckduckgo")
    WebResearch([probe], max_queries=DDG_MAX_QUERIES).search_many([Query(f"q{i}") for i in range(7)])
    assert len(probe.queries) == DDG_MAX_QUERIES


def test_search_time_budget_stops_new_queries():
    probe = FakeProvider("tavily")
    bundle = WebResearch([probe], time_budget_s=0).search_many([Query("a"), Query("b")])
    assert probe.queries == []
    assert "time budget" in bundle.errors[0]


def test_ddg_passes_timeout_to_client(monkeypatch):
    seen = {}

    class FakeDDGS:
        def __init__(self, timeout=None):
            seen["timeout"] = timeout

        def text(self, query, max_results=5):
            return [{"title": "t", "href": "https://x.example", "body": "b"}]

    import ddgs
    monkeypatch.setattr(ddgs, "DDGS", FakeDDGS)
    results = DuckDuckGoSearch(timeout=7).search("q", 3, "general")
    assert seen["timeout"] == 7 and results[0].url == "https://x.example"


# --------------------------------------------------------------------------- FastAPI backend
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path))

    def fake_runner(company, *, url=None, context=None, ui=None, build_prototype=None, from_step=1, slug=None):
        return run_pipeline(company, url=url, context=context, settings=settings(tmp_path), llm=FakeLLM(),
                            research=FakeResearch(), ui=ui, build_prototype=build_prototype, from_step=from_step,
                            slug=slug)

    monkeypatch.setattr(api_module, "RUNNER", fake_runner)
    return TestClient(api_module.app)


def sse_events(body: str) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in body.splitlines() if line.startswith("data: ")]


def test_api_stream_reports_four_stages_and_returns_report(client):
    resp = client.post("/api/analyze/stream", json={"company_name": BUSINESS, "url": "maplestreetdental.example"})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/event-stream")
    events = sse_events(resp.text)
    assert events[0]["type"] == "accepted" and events[-1]["type"] == "result"

    stage_events = [(e["stage"], e["state"]) for e in events if e["type"] == "stage"]
    assert stage_events == [(1, "active"), (1, "done"), (2, "active"), (2, "done"),
                            (3, "active"), (3, "done"), (4, "active"), (4, "done")]
    assert any(e["type"] == "status" and e["stage"] == 3 for e in events)
    assert any(e["type"] == "agent_done" and e["agent"] == "Executive Evaluator" for e in events)

    result = events[-1]
    assert result["report"]["stages_completed"] == [1, 2, 3, 4]
    assert all(h in result["markdown"] for h in SECTION_HEADINGS)
    assert result["pitch_text"].startswith("Filling Maple Street")
    assert result["prototype_url"] == "/api/examples/maple-street-dental/prototype"
    assert result["usage"]["input_tokens"] > 0


def test_api_examples_list_and_load(client):
    client.post("/api/analyze", json={"company_name": BUSINESS, "include_prototype": False})
    runs = client.get("/api/examples").json()
    assert runs[0]["slug"] == "maple-street-dental" and runs[0]["complete"] is True
    data = client.get("/api/examples/maple-street-dental").json()
    assert data["report"]["business_name"] == BUSINESS and data["prototype_url"] is None
    assert client.get("/api/examples/maple-street-dental/prototype").status_code == 404


def test_api_examples_include_legacy_partial_runs(client, tmp_path):
    (tmp_path / "blue-bottle-coffee").mkdir()
    shutil.copy(FIXTURES / "legacy_profile.json", tmp_path / "blue-bottle-coffee" / PROFILE_JSON)
    runs = client.get("/api/examples").json()
    assert runs == [{**runs[0], "slug": "blue-bottle-coffee", "stages_completed": [1], "complete": False}]
    assert client.get("/api/examples/blue-bottle-coffee").status_code == 200


def test_api_serves_prototype(client):
    client.post("/api/analyze", json={"company_name": BUSINESS})
    resp = client.get("/api/examples/maple-street-dental/prototype")
    assert resp.status_code == 200 and "text/html" in resp.headers["content-type"]


@pytest.mark.parametrize("slug,status", [("..", 404), ("Bad Slug", 400), ("missing-run", 404)])
def test_api_rejects_bad_slugs(client, slug, status):
    assert client.get(f"/api/examples/{slug}").status_code == status


def test_api_validates_input(client):
    assert client.post("/api/analyze", json={"company_name": "   "}).status_code == 422
    assert client.post("/api/analyze", json={"company_name": "X", "url": "not a url"}).status_code == 422


def test_api_stream_reports_pipeline_errors(client, monkeypatch):
    def boom(*a, **k):
        from utils.llm import LLMError
        raise LLMError("Gemini blocked the prompt (SAFETY).")

    monkeypatch.setattr(api_module, "RUNNER", boom)
    events = sse_events(client.post("/api/analyze/stream", json={"company_name": "Sobha"}).text)
    assert events[-1] == {"type": "error", "message": "Gemini blocked the prompt (SAFETY)."}
    # The run lock is released, so a retry is accepted.
    assert client.post("/api/analyze/stream", json={"company_name": "Sobha"}).status_code == 200


def test_api_cors_allows_vite_dev_server(client):
    resp = client.options("/api/examples", headers={"Origin": "http://localhost:5173",
                                                    "Access-Control-Request-Method": "GET"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_site_query_always_has_search_terms():
    """Tavily rejects queries made only of site: operators ("Query cannot consist only of site: operators")."""
    from agents.researcher import build_queries
    queries = build_queries("Adani Realty", "adanirealty.com", None)
    site_queries = [q.text for q in queries if "site:" in q.text]
    assert site_queries == ["Adani Realty about projects investors site:adanirealty.com"]
    for q in queries:
        terms = [w for w in q.text.split() if not w.startswith("site:")]
        assert terms, f"query {q.text!r} has no search terms"


def test_api_resume_from_stage_3_reuses_saved_stages(client):
    client.post("/api/analyze", json={"company_name": BUSINESS, "include_prototype": False})
    events = sse_events(client.post("/api/analyze/stream", json={
        "company_name": BUSINESS, "include_prototype": False, "from_stage": 3}).text)
    stage_events = [(e["stage"], e["state"]) for e in events if e["type"] == "stage"]
    assert stage_events[:2] == [(1, "skipped"), (2, "skipped")]
    assert (3, "done") in stage_events and (4, "done") in stage_events
    assert events[-1]["type"] == "result"


def test_api_resume_without_saved_stages_reports_error(client):
    events = sse_events(client.post("/api/analyze/stream", json={"company_name": "Brand New Co", "from_stage": 3}).text)
    assert events[-1]["type"] == "error" and "Cannot start at stage 3" in events[-1]["message"]


def test_model_switch_notes_reach_the_progress_stream(client, monkeypatch, tmp_path):
    def noisy_runner(company, *, ui=None, from_step=1, slug=None, **kw):
        llm = FakeLLM()
        original = llm._structured_once

        def structured_once(**kwargs):
            llm.notify("baidu/ernie:free unavailable (rate-limited); switching to google/gemma:free")
            return original(**kwargs)

        llm._structured_once = structured_once
        return run_pipeline(company, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=ui,
                            build_prototype=False, from_step=from_step)

    monkeypatch.setattr(api_module, "RUNNER", noisy_runner)
    events = sse_events(client.post("/api/analyze/stream", json={"company_name": BUSINESS}).text)
    assert any(e["type"] == "note" and "switching to google/gemma:free" in e["message"] for e in events)


def test_api_resume_by_run_slug_when_display_name_differs(client, tmp_path):
    """outputs/sobha/ holds a run whose report title is "Sobha Limited"; resume must target that folder."""
    client.post("/api/analyze", json={"company_name": "Sobha", "include_prototype": False})
    (tmp_path / "sobha" / "00_run_meta.json").unlink()                 # partial runs have no meta
    for name in ("03_ai_opportunities.json", "03_winning_strategy.json", "04_ceo_pitch.json"):
        (tmp_path / "sobha" / name).unlink()
    runs = {r["slug"]: r for r in client.get("/api/examples").json()}
    assert runs["sobha"]["next_stage"] == 3 and runs["sobha"]["complete"] is False
    events = sse_events(client.post("/api/analyze/stream", json={
        "company_name": "Sobha Limited", "run_slug": "sobha", "from_stage": 3, "include_prototype": False}).text)
    assert events[-1]["type"] == "result" and events[-1]["report"]["slug"] == "sobha"
    assert not (tmp_path / "sobha-limited").exists()


def test_api_examples_report_input_name_and_website(client):
    client.post("/api/analyze", json={"company_name": BUSINESS, "url": "maplestreetdental.example",
                                      "include_prototype": False})
    run = client.get("/api/examples").json()[0]
    assert run["input_name"] == BUSINESS and run["next_stage"] is None
    assert run["website"] == "https://maplestreetdental.example" and run["industry"] == "Healthcare"


def test_api_rejects_bad_run_slug(client):
    assert client.post("/api/analyze", json={"company_name": "X", "run_slug": "../etc"}).status_code == 422


def test_report_opportunities_carry_rubric_scores(tmp_path):
    report = build_report(full_run(tmp_path, build_prototype=False))
    top = report.ai_opportunities[0]
    assert [r.criterion for r in top.rubric] == ["roi_potential", "feasibility", "speed_to_value", "competitive_moat"]
    assert [r.score for r in top.rubric] == [9, 8, 8, 6]          # opp-1 from the fixture
    assert abs(sum(r.weight for r in top.rubric) - 1.0) < 1e-6
    assert top.biggest_risk == "API access" and all(r.rationale for r in top.rubric)
