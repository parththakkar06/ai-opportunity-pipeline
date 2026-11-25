"""Phase 3 (verifier) tests: names, stale figures, supported figures, removals, the one LLM call, pass rate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from agents.base import VERIFY_JSON  # noqa: E402
from agents.provenance import mark_superseded  # noqa: E402
from agents.report import build_report, render_report_markdown  # noqa: E402
from agents.verifier import addressed_person, values, verify_pitch  # noqa: E402
from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import BUSINESS, FIXTURES, FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.schemas import BusinessProfile, ClaimVerdict, ClaimVerdicts, ExecutivePitchDraft, Fact, SourceDoc  # noqa: E402


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


def sobha_profile() -> BusinessProfile:
    facts = mark_superseded([
        Fact(fact_id="S1.F1", source_id="S1", statement="Sobha FY25 revenue was ₹4,163 crore.", metric="revenue",
             value="₹4,163 crore", period="FY25", as_of="2025-03-31"),
        Fact(fact_id="S2.F1", source_id="S2", statement="Sobha FY26 revenue was ₹4,812 crore.", metric="revenue",
             value="₹4,812 crore", period="FY26", as_of="2026-03-31"),
        Fact(fact_id="S2.F2", source_id="S2", statement="Sobha re-appointed Jagadish Nangineni as Managing Director.",
             metric="managing_director", as_of="2026-07-18"),
        Fact(fact_id="S2.F3", source_id="S2", statement="Sobha sold 1.2 mn sq ft in Q1 FY27.", metric="area_sold",
             value="1.2 mn sq ft", period="Q1 FY27", as_of="2026-06-30"),
    ])
    data = json.loads((FIXTURES / "BusinessProfileDraft.json").read_text())
    return BusinessProfile.model_validate({
        **data, "business_name": "Sobha Limited", "facts": facts,
        "leadership": ["Jagadish Nangineni — Managing Director"],
        "leaders": [{"name": "Jagadish Nangineni", "role": "Managing Director", "evidence": ["S2.F2"]}],
        "sources_index": [SourceDoc(source_id="S1", url="u1", title="FY25 annual report", source_type="filing", kind="pdf"),
                          SourceDoc(source_id="S2", url="u2", title="Q1 FY27 update", source_type="investor", kind="pdf")],
        "provenance_warnings": ["Leader 'Francis Alfred' (Managing Director) dropped: superseded by newer evidence S2.F2"],
    })


def pitch(**over) -> ExecutivePitchDraft:
    data = json.loads((FIXTURES / "ExecutivePitchDraft.json").read_text())
    data.update(recipient_role="Managing Director", addressed_to="Mr. Francis Alfred, Managing Director",
                why_we_reached_out="Sobha posted FY2025 revenue of ₹4,163 crore. You sold 1.2 mn sq ft in Q1 FY27.",
                email_body="Dear Mr. Alfred,\n\nCongratulations on a strong quarter.\n\n[Your Name]",
                elevator_pitch="We help developers convert more site visits.",
                opportunities_identified=[{"title": "Lead follow-up", "evidence": "Reviews mention slow callbacks."}],
                recommended_solutions=[{"name": "Lead scoring", "what_it_does": "Ranks enquiries.", "maps_to": "Sales",
                                        "expected_impact": "Could lift conversion by 12%", "timeline": "6 weeks"}],
                closing="Open to a 30-minute walkthrough?")
    data.update(over)
    return ExecutivePitchDraft.model_validate(data)


def by_text(report, text):
    return next(c for c in report.claims if c.text == text)


# ------------------------------------------------------------------------------------------- names
def test_wrong_md_is_replaced_with_title_everywhere():
    """Regression: the Sobha pitch addressed 'Francis Alfred, Managing Director'."""
    fixed, rep = verify_pitch(pitch(), sobha_profile())
    c = by_text(rep, "Francis Alfred")
    assert c.status == "unsupported" and c.action == "replaced"
    assert fixed.addressed_to == "Managing Director"
    assert "Alfred" not in fixed.email_body and fixed.email_body.startswith("Dear Managing Director")
    assert any("Replaced 'Francis Alfred'" in a for a in rep.actions)


def test_current_md_passes():
    fixed, rep = verify_pitch(pitch(addressed_to="Mr. Jagadish Nangineni, Managing Director",
                                    email_body="Dear Mr. Nangineni,\n\nHello."), sobha_profile())
    c = by_text(rep, "Jagadish Nangineni")
    assert c.status == "supported" and c.evidence == ["S2.F2"]
    assert fixed.addressed_to == "Mr. Jagadish Nangineni, Managing Director"


@pytest.mark.parametrize("text,person", [
    ("Mr. Francis Alfred, Managing Director", "Francis Alfred"),
    ("Managing Director & CEO", None),
    ("Dr. Priya Patel, Founder & CEO", "Priya Patel"),
    ("The Leadership Team", None),
])
def test_addressed_person(text, person):
    assert addressed_person(text) == person


# ------------------------------------------------------------------------------------------- figures and periods
def test_stale_fy2025_figure_is_flagged_when_fy2026_exists():
    _fixed, rep = verify_pitch(pitch(), sobha_profile())
    c = by_text(rep, "₹4,163 crore")
    assert c.status == "stale" and c.action == "flagged" and "S2.F1" in c.evidence and "4,812" in c.note
    period = by_text(rep, "FY2025")
    assert period.status == "stale" and period.evidence == ["S2.F1"]


def test_supported_figure_passes():
    _fixed, rep = verify_pitch(pitch(), sobha_profile())
    c = by_text(rep, "1.2 mn sq ft")
    assert c.status == "supported" and c.evidence == ["S2.F3"] and c.action == "kept"
    assert by_text(rep, "Q1 FY27").status == "supported"


def test_projection_figures_are_estimates_not_claims():
    _fixed, rep = verify_pitch(pitch(), sobha_profile())
    assert by_text(rep, "12%").status == "estimate"


def test_unsupported_figure_removed_from_factual_paragraph():
    why = "Sobha sold 1.2 mn sq ft in Q1 FY27. Sobha has 9,400 employees across India."
    fixed, rep = verify_pitch(pitch(why_we_reached_out=why), sobha_profile())
    c = by_text(rep, "9,400 employees")
    assert c.status == "unsupported" and c.action == "removed"
    assert fixed.why_we_reached_out == "Sobha sold 1.2 mn sq ft in Q1 FY27."


def test_unsupported_figure_is_flagged_not_removed_when_it_is_the_whole_paragraph():
    fixed, rep = verify_pitch(pitch(why_we_reached_out="Sobha has 9,400 employees."), sobha_profile())
    assert by_text(rep, "9,400 employees").action == "flagged" and fixed.why_we_reached_out


def test_values_normalization():
    assert values("₹4,163 crore") == ["4163"] and values("FY2025") == [] and values("12%") == ["12"]
    assert values("Q1 FY27 sales of 2,700 units") == ["2700"]


# ------------------------------------------------------------------------------------------- the one LLM call
class Judge:
    def __init__(self, verdicts):
        self.verdicts, self.calls = verdicts, 0

    def structured(self, **kw):
        self.calls += 1
        assert kw["schema"] is ClaimVerdicts and "<claims>" in kw["user"]
        return ClaimVerdicts(verdicts=[ClaimVerdict(**v) for v in self.verdicts(kw["user"])])


def test_leftovers_go_to_one_cheap_call():
    why = "Sobha sold 1.2 mn sq ft in Q1 FY27. It has 9,400 employees. It launched 3,100 units."
    judge = Judge(lambda user: [{"claim_id": cid, "verdict": v, "fact_ids": ids} for cid, v, ids in
                                (("C2", "yes", ["S2.F3"]), ("C3", "partial", []))])
    _fixed, rep = verify_pitch(pitch(why_we_reached_out=why, addressed_to="Managing Director", email_body="Hi."),
                               sobha_profile(), llm=judge, model="cheap")
    assert judge.calls == 1 and rep.llm_checked == 2
    statuses = {c.text: c.status for c in rep.claims}
    assert statuses["9,400 employees"] == "supported" and statuses["3,100 units"] == "partial"


def test_no_llm_call_when_everything_resolves():
    judge = Judge(lambda user: [])
    verify_pitch(pitch(why_we_reached_out="Sobha sold 1.2 mn sq ft in Q1 FY27."), sobha_profile(), llm=judge,
                 model="cheap")
    assert judge.calls == 0


def test_pass_rate_math():
    why = "Sobha posted ₹4,163 crore in FY2025. It sold 1.2 mn sq ft in Q1 FY27. It has 9,400 employees."
    _fixed, rep = verify_pitch(pitch(why_we_reached_out=why), sobha_profile())
    # name (unsupported), ₹4,163 crore (stale), FY2025 (stale), 1.2 mn sq ft, Q1 FY27 (supported), 9,400 (unsupported)
    assert rep.checked == 6 and rep.supported == 2 and rep.pass_rate == pytest.approx(0.333, abs=0.001)
    assert rep.estimates == 1                                # "could lift conversion by 12%"
    empty, none = verify_pitch(pitch(addressed_to="Managing Director", email_body="Hi.", why_we_reached_out="Hello.",
                                     recommended_solutions=[]), sobha_profile())
    assert none.checked == 0 and none.pass_rate is None


# ------------------------------------------------------------------------------------------- pipeline
def test_pipeline_writes_verification_and_report_shows_it(tmp_path):
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    out = tmp_path / "maple-street-dental"
    v = json.loads((out / VERIFY_JSON).read_text())
    assert v["checked"] >= 1 and 0 <= v["pass_rate"] <= 1
    report = build_report(out)
    assert report.verification and report.verification.checked == v["checked"]
    assert "**Verification:**" in render_report_markdown(report)
