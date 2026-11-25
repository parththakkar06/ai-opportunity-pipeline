"""Phase 6 (traceability) tests: every pitch line cites a resolvable source, no orphan citations, the chain."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from agents.report import build_report, render_report_markdown  # noqa: E402
from agents.trace import _Matcher  # noqa: E402
from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import BUSINESS, FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.schemas import BusinessChallenges, ExecutivePitchDraft, Fact  # noqa: E402

EVIDENCED = "Maple Street Dental serves about 6,500 active patients who are due for orthodontic follow-up."


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


def run(tmp_path, llm=None):
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=llm or FakeLLM(), research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    return build_report(tmp_path / "maple-street-dental")


def assert_integrity(report):
    nums = [c.n for c in report.citations]
    assert nums == list(range(1, len(nums) + 1))                                  # contiguous [1]..[N]
    sources = {c.source_id for c in report.citations}
    assert len(sources) == len(nums)                                              # one number per source
    used = {n for node in report.trace.nodes for n in node.citations}
    assert used <= set(nums), "orphan citation number"
    assert set(nums) <= used, "citation listed but never used"
    ids = {n.id for n in report.trace.nodes}
    assert all(e.source in ids and e.target in ids for e in report.trace.edges)
    facts = {n.id for n in report.trace.nodes if n.kind == "fact"}
    assert all(f in facts for n in report.trace.nodes for f in n.facts if "." in f or f.startswith("R"))


def test_trace_integrity_and_honest_uncited_line(tmp_path):
    report = run(tmp_path)
    assert_integrity(report)
    nodes = {n.id: n for n in report.trace.nodes}
    factual = [n for n in report.trace.nodes if n.kind == "pitch" and not n.id.startswith("pitch-sol")]
    for n in factual:
        assert n.citations or n.id in report.trace.uncited
    # The fixture's "Invisalign is a core high-ticket service" has no source, and the trace says so.
    assert report.trace.uncited == ["pitch-opp-3"]
    assert nodes["pitch-opening"].citations                                        # the CEO quote cites its doc
    assert nodes["pitch-opp-1"].facts and nodes["pitch-why-1"].citations


def test_every_pitch_sentence_has_a_resolvable_citation(tmp_path):
    class Evidenced(FakeLLM):
        def _structured_once(self, **kw):
            result = super()._structured_once(**kw)
            if kw["schema"] is ExecutivePitchDraft:
                result.opportunities_identified[2].evidence = EVIDENCED
            return result

    report = run(tmp_path, Evidenced())
    assert_integrity(report)
    by_n = {c.n: c for c in report.citations}
    pitch = [n for n in report.trace.nodes if n.kind == "pitch"]
    assert pitch and report.trace.uncited == []
    for n in pitch:
        assert n.citations, n.label
        assert all(by_n[c].url.startswith("https://") for c in n.citations)


def test_chain_fact_to_challenge_to_opportunity_to_pitch(tmp_path):
    report = run(tmp_path)
    edges = {(e.source, e.target) for e in report.trace.edges}
    assert ("ch-1", "opp-1") in edges                                             # opportunity solves challenge
    assert any(t == "ch-1" and s.startswith("S") for s, t in edges)               # a fact supports the challenge
    assert ("opp-1", "pitch-sol-1") in edges or ("opp-1", "pitch-opp-1") in edges  # the idea reaches the pitch
    assert ("ch-1", "pitch-why-2") in edges                                        # shared review fact


def test_explicit_fact_ids_win_and_superseded_facts_are_not_matched():
    facts = [Fact(fact_id="S1.F1", source_id="S1", statement="Acme opened a new plant in Pune in 2026."),
             Fact(fact_id="S1.F2", source_id="S1", statement="Acme revenue was 400 crore.", superseded_by="S2.F1"),
             Fact(fact_id="S2.F1", source_id="S2", statement="Acme revenue was 480 crore in FY26.")]
    m = _Matcher(facts, "Acme")
    assert m.find("Per S1.F2, the plant matters") == ["S1.F2"]                    # cited id taken as written
    assert m.find("New plant opened in Pune") == ["S1.F1"]
    assert "S1.F2" not in m.find("revenue was 400 crore")                          # superseded never matched
    assert m.find("Unrelated sentence about weather") == []


def test_markdown_has_numbered_footnotes(tmp_path):
    report = run(tmp_path)
    md = render_report_markdown(report)
    assert "Invisalign is a core high-ticket service [no source]" in md
    assert "### Sources" in md and f"1. [{report.citations[0].title}]({report.citations[0].url})" in md
    challenges = BusinessChallenges.model_validate({"business_name": "x", "challenges": [
        c.model_dump() for c in report.business_challenges]})
    cited = next(n for n in report.trace.nodes if n.kind == "challenge" and n.citations)
    title = next(c.title for c in challenges.challenges if c.id == cited.id)
    assert f"{title} [{cited.citations[0]}]" in md
