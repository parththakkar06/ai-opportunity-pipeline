"""Phase 1 (deep research) tests: offline, fixture-based, no API keys."""
from __future__ import annotations

import io
import json
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.base import PROFILE_JSON  # noqa: E402
from agents.provenance import (  # noqa: E402
    detect_gaps, document_facts, format_evidence, gap_queries, mark_superseded, snippet_sources, validate_profile,
)
from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import BUSINESS, FIXTURES, FakeLLM, FakeProvider, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.cache import DiskCache  # noqa: E402
from utils.config import Settings  # noqa: E402
from utils.dates import months_old, parse_as_of  # noqa: E402
from utils.fetch import fetch_document  # noqa: E402
from utils.schemas import BusinessProfile, BusinessProfileDraft, DocFacts, ExtractedFact, Fact, SourceDoc  # noqa: E402
from utils.search import Query, SearchResult, WebResearch  # noqa: E402
from utils.sources import classify, rank_sources  # noqa: E402

TODAY = date(2026, 11, 25)


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


def draft(**overrides) -> BusinessProfileDraft:
    data = json.loads((FIXTURES / "BusinessProfileDraft.json").read_text())
    data.update(overrides)
    return BusinessProfileDraft.model_validate(data)


def fact(fid, statement, as_of, metric=None, period=None, value=None, basis="stated") -> Fact:
    return Fact(fact_id=fid, source_id=fid.split(".")[0], statement=statement, as_of=as_of, metric=metric,
                period=period, value=value, as_of_basis=basis)


# ------------------------------------------------------------------------------------------- dates
@pytest.mark.parametrize("text,expected", [
    ("FY26", "2026-03-31"),
    ("FY2025-26", "2026-03-31"),
    ("Q1 FY27", "2026-06-30"),
    ("Q3FY26 operational update", "2025-12-31"),
    ("12 May 2026", "2026-05-12"),
    ("July 15, 2026", "2026-07-15"),
    ("2026-08-04T10:00:00Z", "2026-08-04"),
    ("https://x.com/news/2026/07/md-reappointed", "2026-07-01"),
    ("no date here", None),
])
def test_parse_as_of_understands_indian_fiscal_periods(text, expected):
    assert parse_as_of(text) == expected


def test_months_old():
    assert months_old("2026-05-25", TODAY) == pytest.approx(6.0, abs=0.1)
    assert months_old(None, TODAY) is None


# ------------------------------------------------------------------------------------------- source ranking
def sr(url, title="t", date_=None):
    return SearchResult(title=title, url=url, snippet="s", provider="tavily", query="q", date=date_)


def test_rank_prefers_primary_recent_sources_and_caps_per_domain():
    results = [
        sr("https://www.facebook.com/sobha/posts/1"),
        sr("https://blog.example.org/sobha-review"),
        sr("https://economictimes.indiatimes.com/sobha-md-2026", date_="2026-07-20"),
        sr("https://economictimes.indiatimes.com/sobha-results", date_="2025-02-01"),
        sr("https://economictimes.indiatimes.com/sobha-old", date_="2024-01-01"),
        sr("https://www.sobha.com/investors/q1-fy27-update.pdf"),
        sr("https://www.bseindia.com/xml-data/corpfiling/sobha.pdf"),
    ]
    ranked = rank_sources(results, "sobha.com", limit=6)
    kinds = [c.source_type for c in ranked]
    assert set(kinds[:2]) == {"filing", "investor"}
    assert "low" not in kinds and all("facebook" not in c.result.url for c in ranked)
    assert sum("economictimes" in c.result.url for c in ranked) == 2                  # per-domain cap
    news = [c.result.url for c in ranked if c.source_type == "news"]
    assert news[0].endswith("sobha-md-2026")                                         # newest news first


def test_classify():
    assert classify(sr("https://www.sobha.com/investor-relations"), "sobha.com") == "investor"
    assert classify(sr("https://www.sobha.com/projects"), "sobha.com") == "company"
    assert classify(sr("https://maharera.maharashtra.gov.in/x"), "sobha.com") == "rera"


# ------------------------------------------------------------------------------------------- fetching
def _pdf_bytes(text: str) -> bytes:
    """A minimal valid one-page PDF containing `text` (no PDF library needed)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def test_fetch_reads_pdf_text(monkeypatch):
    body = _pdf_bytes("Sobha Q1 FY27 sales bookings were Rs 2700 crore. " * 12)
    monkeypatch.setattr(httpx, "get", lambda url, **kw: httpx.Response(
        200, content=body, headers={"content-type": "application/pdf"}, request=httpx.Request("GET", url)))
    doc = fetch_document("https://www.sobha.com/investors/q1fy27.pdf")
    assert doc.ok and doc.kind == "pdf" and "sales bookings" in doc.text


def test_fetch_reads_html_and_published_date(monkeypatch):
    html = ("<html><head><title>MD re-appointed</title><meta property='article:published_time' content='2026-07-18'>"
            "</head><body><nav>menu</nav><article>" + "<p>Sobha re-appointed its Managing Director.</p>" * 20
            + "</article><script>x()</script></body></html>")
    monkeypatch.setattr(httpx, "get", lambda url, **kw: httpx.Response(
        200, text=html, headers={"content-type": "text/html"}, request=httpx.Request("GET", url)))
    doc = fetch_document("https://news.example/sobha-md")
    assert doc.ok and doc.published == "2026-07-18" and "menu" not in doc.text and "x()" not in doc.text


def test_fetch_reports_blocked_pages(monkeypatch):
    def blocked(url, **kw):
        raise httpx.HTTPStatusError("403 Forbidden", request=httpx.Request("GET", url),
                                    response=httpx.Response(403, request=httpx.Request("GET", url)))
    monkeypatch.setattr(httpx, "get", blocked)
    doc = fetch_document("https://www.nseindia.com/x.pdf")
    assert not doc.ok and "HTTPStatusError" in doc.error


# ------------------------------------------------------------------------------------------- provenance
def test_wrong_md_regression_newest_leader_wins():
    """The Sobha bug: an old MD from stale evidence must not survive when a newer source names someone else."""
    facts = mark_superseded([
        fact("S1.F1", "Francis Alfred is the Managing Director of Sobha Limited.", "2024-05-10", metric="managing_director"),
        fact("S2.F1", "Sobha re-appointed Jagadish Nangineni as Managing Director.", "2026-07-18", metric="managing_director"),
    ])
    assert facts[0].superseded_by == "S2.F1"
    d = draft(leaders=[{"name": "Francis Alfred", "role": "Managing Director", "evidence": ["S1.F1"]},
                       {"name": "Jagadish Nangineni", "role": "Managing Director", "evidence": ["S2.F1"]}])
    p = validate_profile(d, [], facts, today=TODAY)
    assert p.leadership == ["Jagadish Nangineni — Managing Director"]
    assert any("Francis Alfred" in w and "superseded" in w for w in p.provenance_warnings)


def test_stale_or_unsupported_leaders_become_unknown():
    facts = [fact("S1.F1", "Francis Alfred is the Managing Director.", "2024-05-10", metric="managing_director"),
             fact("S1.F2", "The company reported FY26 results.", "2026-05-01")]
    d = draft(leaders=[{"name": "Francis Alfred", "role": "Managing Director", "evidence": ["S1.F1"]},
                       {"name": "Someone Else", "role": "CFO", "evidence": ["S1.F2"]}])
    p = validate_profile(d, [], facts, today=TODAY)
    assert p.leadership == []
    assert any("older than 12 months" in w for w in p.provenance_warnings)
    assert any("no cited fact names this person" in w for w in p.provenance_warnings)
    assert any("Managing Director: current holder unknown" in a for a in p.assumptions)


def test_undated_leader_evidence_is_rejected_but_live_company_pages_count():
    undated = [fact("S1.F1", "Priya Patel is CEO.", None, metric="ceo", basis="unknown")]
    live = [fact("S1.F1", "Priya Patel is CEO.", TODAY.isoformat(), metric="ceo", basis="retrieved")]
    d = draft(leaders=[{"name": "Priya Patel", "role": "CEO", "evidence": ["S1.F1"]}])
    assert validate_profile(d, [], undated, today=TODAY).leadership == []
    assert validate_profile(d, [], live, today=TODAY).leadership == ["Priya Patel — CEO"]


def test_newest_wins_only_within_same_metric_and_period_type():
    facts = mark_superseded([
        fact("S1.F1", "FY25 revenue ₹4,163 crore", "2025-03-31", metric="revenue", period="FY25"),
        fact("S2.F1", "FY26 revenue ₹4,800 crore", "2026-03-31", metric="revenue", period="FY26"),
        fact("S2.F2", "Q1 FY27 revenue ₹1,300 crore", "2026-06-30", metric="revenue", period="Q1 FY27"),
    ])
    assert facts[0].superseded_by == "S2.F1"       # annual replaced by newer annual
    assert facts[1].superseded_by is None          # quarterly doesn't replace annual
    text = format_evidence([SourceDoc(source_id="S1", url="u", title="t", source_type="investor", kind="pdf"),
                            SourceDoc(source_id="S2", url="v", title="t2", source_type="investor", kind="pdf")], facts)
    assert "[superseded by S2.F1]" in text


def test_unsupported_figures_are_removed():
    facts = [fact("S1.F1", "The practice has 14 chairs and 22 staff.", "2026-06-01")]
    d = draft(scale={"revenue": "FY25 revenue ₹4,163 crore", "projects_or_portfolio": "2 clinics, 14 chairs",
                     "employees": "22", "other_metrics": ["Market cap ₹13,116 crore"]})
    p = validate_profile(d, [], facts, today=TODAY)
    assert p.scale.revenue is None and p.scale.projects_or_portfolio == "2 clinics, 14 chairs"
    assert p.scale.employees == "22" and p.scale.other_metrics == []
    assert any("figure not found in the evidence" in w for w in p.provenance_warnings)


def test_unknown_evidence_ids_are_dropped():
    d = draft(field_evidence=[{"field": "scale.revenue", "evidence": ["S9.F9", "S1.F1"]}])
    p = validate_profile(d, [], [fact("S1.F1", "FY25 revenue was $9 million and 14 chairs, 22 staff, 6,500 patients", "2026-01-01")],
                         today=TODAY)
    assert p.field_evidence[0].evidence == ["S1.F1"]


def test_document_facts_resolve_dates():
    src = SourceDoc(source_id="S2", url="u", title="t", source_type="investor", kind="pdf", published=None,
                    retrieved="2026-11-25")
    df = DocFacts(source_id="S2", document_date=None, facts=[
        ExtractedFact(statement="a", as_of="2026-07-01"), ExtractedFact(statement="b", period="Q1 FY27"),
        ExtractedFact(statement="c")])
    fs = document_facts(df, src)
    assert [f.fact_id for f in fs] == ["S2.F1", "S2.F2", "S2.F3"]
    assert [(f.as_of, f.as_of_basis) for f in fs] == [("2026-07-01", "stated"), ("2026-06-30", "stated"),
                                                       ("2026-11-25", "retrieved")]


def test_gap_detection_and_queries():
    p = BusinessProfile.model_validate({**json.loads((FIXTURES / "BusinessProfileDraft.json").read_text()),
                                        "leadership": [], "recent_news": []})
    gaps = detect_gaps(p, TODAY)
    assert "leadership" in gaps and "recent_news" in gaps and "financials" in gaps
    qs = gap_queries("Sobha", gaps, year=2026)
    assert len(qs) <= 4 and any("managing director" in q.text for q in qs)


# ------------------------------------------------------------------------------------------- stage 1 end to end
def test_research_stage_reads_documents_and_cites_facts(tmp_path):
    research = FakeResearch()
    run_pipeline(BUSINESS, url="maplestreetdental.example", settings=settings(tmp_path), llm=FakeLLM(),
                 research=research, ui=quiet_ui(), build_prototype=False)
    out = tmp_path / "maple-street-dental"
    profile = BusinessProfile.model_validate_json((out / PROFILE_JSON).read_text())
    assert profile.leadership == ["Dr. Priya Patel — Founder & CEO"]
    assert profile.facts and all(f.fact_id and f.source_id for f in profile.facts)
    docs = [s for s in profile.sources_index if s.kind != "snippet"]
    assert 1 <= len(docs) <= 6 and docs[0].source_type == "investor"
    assert profile.leader_statements and profile.leader_statements[0]["source_id"].startswith("S")
    meta = json.loads((out / "00_run_meta.json").read_text())
    assert meta["research"]["documents"] == len(docs) and meta["stages"]["1"]["calls"] >= 2
    assert (out / "cache" / "pages").is_dir() and (out / "cache" / "facts").is_dir()


def test_rerun_uses_cache_and_costs_no_research_tokens(tmp_path):
    first = FakeResearch()
    run_pipeline(BUSINESS, url="maplestreetdental.example", settings=settings(tmp_path), llm=FakeLLM(),
                 research=first, ui=quiet_ui(), build_prototype=False)
    second_llm, second = FakeLLM(), FakeResearch()
    calls = {"search": 0}
    original = second.providers[0].search

    def counting_search(*a, **k):
        calls["search"] += 1
        return original(*a, **k)

    second.providers[0].search = counting_search
    run_pipeline(BUSINESS, url="maplestreetdental.example", settings=settings(tmp_path), llm=second_llm,
                 research=second, ui=quiet_ui(), build_prototype=False)
    assert calls["search"] == 0                      # all queries served from cache
    assert second.documents_fetched == []            # no page fetched again
    assert "FactBatch" not in second_llm.calls       # no extraction call again


def test_refresh_bypasses_cache(tmp_path):
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    llm = FakeLLM()
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False, refresh=True)
    assert "FactBatch" in llm.calls


def test_gap_round_skipped_when_data_quality_high(tmp_path):
    class HighQuality(FakeLLM):
        def _structured_once(self, **kw):
            result = super()._structured_once(**kw)
            if kw["schema"] is BusinessProfileDraft:
                result.data_quality = "high"
            return result

    llm = HighQuality()
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    assert llm.calls.count("BusinessProfileDraft") == 1
    meta = json.loads((tmp_path / "maple-street-dental" / "00_run_meta.json").read_text())
    assert meta["research"]["gap_round"] is False


def test_extraction_is_batched(tmp_path):
    llm = FakeLLM()
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    meta = json.loads((tmp_path / "maple-street-dental" / "00_run_meta.json").read_text())
    docs = meta["research"]["documents"]
    assert llm.calls.count("FactBatch") <= -(-docs // 3) + 1        # ≤ ceil(docs/3) + one gap batch


def test_keyless_search_path_still_works(tmp_path):
    """No API keys: DuckDuckGo-only chain, no Tavily fetch fallback, pipeline completes."""
    keyless = WebResearch.from_settings(Settings())
    assert keyless.provider_names == ["duckduckgo"] and keyless.tavily_client is None
    research = FakeResearch([FakeProvider("duckduckgo")])
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=FakeLLM(), research=research, ui=quiet_ui(),
                 build_prototype=False)
    meta = json.loads((tmp_path / "maple-street-dental" / "00_run_meta.json").read_text())
    assert meta["search_providers_used"] == ["duckduckgo"]


def test_search_cache_round_trip(tmp_path):
    cache = DiskCache(tmp_path)
    provider = FakeProvider("tavily")
    research = WebResearch([provider], results_per_query=3)
    a = research.search_many([Query("Sobha results")], cache=cache)
    b = research.search_many([Query("Sobha results")], cache=cache)
    assert len(provider.queries) == 1 and [r.url for r in a.results] == [r.url for r in b.results]
    assert b.providers_used == ["tavily"]
