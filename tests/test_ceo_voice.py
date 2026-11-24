"""Phase 2 (CEO voice) tests: verbatim quotes, stated priorities, the pitch-opening rule and its fallback."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from agents.base import PITCH_JSON, PITCH_MD, PROFILE_JSON  # noqa: E402
from agents.ceo_voice import (  # noqa: E402
    invented_quotes, is_verbatim, pitch_opening, stated_priorities, verify_statements,
)
from agents.report import build_report  # noqa: E402
from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import BUSINESS, FIXTURES, FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.schemas import BusinessProfile, ExecutivePitchDraft, FactBatch, Fact, LeaderStatement, SourceDoc  # noqa: E402

TODAY = date(2026, 11, 25)
SOURCE = (FIXTURES / "investor_update.txt").read_text()
QUOTE = "Filling every hygiene chair is our number one priority this year"


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


def stmt(quote, speaker="Dr. Priya Patel", role="Founder & CEO", date_=None):
    return LeaderStatement(speaker=speaker, role=role, quote=quote, topic="utilization", date=date_)


def profile(statements, leadership=("Dr. Priya Patel — Founder & CEO",), published="2026-09-01", facts=()):
    data = json.loads((FIXTURES / "BusinessProfileDraft.json").read_text())
    return BusinessProfile.model_validate({
        **data, "leadership": list(leadership), "facts": list(facts),
        "sources_index": [SourceDoc(source_id="S1", url="https://x.example/q2", title="Q2 investor update",
                                    source_type="investor", kind="pdf", published=published)],
        "leader_statements": [{**s.model_dump(), "source_id": "S1"} for s in statements],
    })


# ------------------------------------------------------------------------------------------- verbatim check
def test_exact_quote_passes_with_typographic_differences():
    assert is_verbatim(QUOTE, SOURCE)
    assert is_verbatim("“Filling every  hygiene\nchair is our number one priority this year.”", SOURCE)


@pytest.mark.parametrize("quote", [
    "Filling every hygiene chair is our top priority this year",      # one word changed
    "Our number one priority this year is filling every hygiene chair",  # reordered
    "We will open a third location in Cedar Park in 2027",             # paraphrase of reported speech
    "priority this year",                                              # too short to be meaningful
])
def test_paraphrased_or_trivial_quotes_are_rejected(quote):
    assert not is_verbatim(quote, SOURCE)


def test_verify_statements_counts_drops():
    kept, dropped = verify_statements([stmt(QUOTE), stmt("Filling chairs is our top priority for this year")], SOURCE)
    assert [s.quote for s in kept] == [QUOTE] and dropped == 1


# ------------------------------------------------------------------------------------------- stated priorities
def test_stated_priority_from_current_leader():
    ps = stated_priorities(profile([stmt(QUOTE)]), today=TODAY)
    assert len(ps) == 1 and ps[0].quote == QUOTE and ps[0].source_id == "S1" and ps[0].date == "2026-09-01"


def test_former_leader_quote_is_not_a_priority():
    """Wrong-MD guard: a quote by someone who isn't in current leadership can't open the pitch."""
    old = stmt("We will double our land bank in the next five years", speaker="Francis Alfred",
               role="Managing Director")
    assert stated_priorities(profile([old], leadership=("Jagadish Nangineni — Managing Director",)), today=TODAY) == []


def test_stale_or_non_executive_quotes_are_not_priorities():
    assert stated_priorities(profile([stmt(QUOTE)], published="2025-01-10"), today=TODAY) == []
    assert stated_priorities(profile([stmt(QUOTE, speaker="Sam Lee", role="Office Manager")],
                                     leadership=()), today=TODAY) == []


def test_opening_quotes_the_ceo_and_cites_source():
    p = profile([stmt(QUOTE)])
    p.stated_priorities = stated_priorities(p, today=TODAY)
    o = pitch_opening(p, "Dr. Priya Patel, Founder & CEO")
    assert o.kind == "stated_priority" and o.source_id == "S1"
    assert o.text == f'In Q2 investor update (1 September 2026), you said: "{QUOTE}"'
    assert "Dr. Priya Patel said" in pitch_opening(p, "Managing Director").text


def test_opening_falls_back_to_newest_current_fact():
    facts = [Fact(fact_id="S1.F1", source_id="S1", statement="Maple Street opened Round Rock.", as_of="2026-04-01"),
             Fact(fact_id="S1.F2", source_id="S1", statement="Maple Street added 4 chairs.", as_of="2026-08-01",
                  metric="chairs"),
             Fact(fact_id="S1.F3", source_id="S1", statement="Old figure.", as_of="2026-10-01",
                  superseded_by="S1.F2")]
    o = pitch_opening(profile([], facts=facts))
    assert o.kind == "newest_fact" and o.source_id == "S1.F2" and o.text.startswith("Maple Street added 4 chairs")
    assert pitch_opening(profile([])) is None


def test_invented_quotes_detected():
    p = profile([stmt(QUOTE)])
    assert invented_quotes(f'As you put it, "{QUOTE}".', p) == []
    assert invented_quotes('You told investors "growth at any cost is over for us".', p)


# ------------------------------------------------------------------------------------------- pipeline
def run(tmp_path, llm):
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    return tmp_path / "maple-street-dental"


def test_pipeline_pitch_opens_on_verified_priority(tmp_path):
    out = run(tmp_path, FakeLLM())
    prof = BusinessProfile.model_validate_json((out / PROFILE_JSON).read_text())
    assert [p.quote for p in prof.stated_priorities] == [QUOTE]
    pitch = json.loads((out / PITCH_JSON).read_text())
    assert pitch["opening"]["kind"] == "stated_priority" and pitch["opening"]["source_id"] == "S1"
    md = (out / PITCH_MD).read_text()
    assert f'you said: "{QUOTE}" [S1]' in md and "No CEO statements found" not in md
    report = build_report(out)
    assert report.ceo_pitch.ceo_statements_found and report.ceo_pitch.opening.quote == QUOTE


def test_paraphrased_quote_from_model_is_dropped_and_pitch_falls_back(tmp_path):
    class Paraphrasing(FakeLLM):
        def _structured_once(self, **kw):
            result = super()._structured_once(**kw)
            if kw["schema"] is FactBatch:
                for d in result.documents:
                    for s in d.leader_statements:
                        s.quote = "Our top priority this year is keeping every hygiene chair full"
            return result

    out = run(tmp_path, Paraphrasing())
    prof = BusinessProfile.model_validate_json((out / PROFILE_JSON).read_text())
    assert prof.leader_statements == [] and prof.stated_priorities == []
    meta = json.loads((out / "00_run_meta.json").read_text())
    assert meta["research"]["quotes_dropped"] >= 1
    pitch = json.loads((out / PITCH_JSON).read_text())
    assert pitch["opening"]["kind"] == "newest_fact"
    assert "No CEO statements found" in (out / PITCH_MD).read_text()
    assert build_report(out).ceo_pitch.ceo_statements_found is False


def test_pitch_with_invented_quote_is_repaired(tmp_path):
    class Inventing(FakeLLM):
        first = True

        def _structured_once(self, **kw):
            result = super()._structured_once(**kw)
            if kw["schema"] is ExecutivePitchDraft and self.first:
                self.first = False
                result.why_we_reached_out = 'You said "we must win every first-time patient this year".'
            return result

    llm = Inventing()
    out = run(tmp_path, llm)
    assert llm.calls.count("ExecutivePitchDraft") == 2
    assert "we must win every first-time patient" not in (out / PITCH_MD).read_text()
    assert "<pitch_opening>" in llm.prompts["ExecutivePitchDraft"]
