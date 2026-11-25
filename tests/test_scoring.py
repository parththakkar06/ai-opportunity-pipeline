"""Phase 4 (better scoring) tests: weights, confidence adjustment, sensitivity, the Sobha regression."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from agents.base import STRATEGY_JSON  # noqa: E402
from agents.evaluator import (  # noqa: E402
    adjusted_roi, evidence_share, rank_opportunities, sensitivity, weighted_score,
)
from agents.report import build_report, render_report_markdown  # noqa: E402
from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import BUSINESS, FIXTURES, FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.config import RubricWeights, load_settings  # noqa: E402
from utils.schemas import AIOpportunities, EvaluationScores, OpportunityScore, WinningStrategy  # noqa: E402

BASE_OPP = json.loads((FIXTURES / "AIOpportunities.json").read_text())["opportunities"][0]


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


def opp(oid, title, effort="medium", low=50_000, high=60_000):
    o = copy.deepcopy(BASE_OPP)
    o.update(id=oid, title=title)
    o["estimated_effort"]["level"] = effort
    o["estimated_impact"].update(annual_value_usd_low=low, annual_value_usd_high=high)
    return o


def score(oid, roi, ceo, feas=7, speed=7, moat=6, drivers=(("public data", ["S1.F1"]),)):
    c = lambda n: {"score": n, "rationale": "r"}  # noqa: E731
    return {"opportunity_id": oid, "roi_potential": c(roi), "ceo_relevance": c(ceo), "feasibility": c(feas),
            "speed_to_value": c(speed), "competitive_moat": c(moat), "biggest_risk": "x",
            "value_drivers": [{"driver": f"d{i}", "source": s, "evidence": e} for i, (s, e) in enumerate(drivers)]}


def build(opps, scores):
    return (AIOpportunities.model_validate({"business_name": "Sobha", "opportunities": opps}),
            EvaluationScores.model_validate({"scores": scores}))


# ------------------------------------------------------------------------------------------- weights
def test_weights_sum_to_one_and_defaults():
    w = RubricWeights().as_dict()
    assert sum(w.values()) == pytest.approx(1.0)
    assert w == {"roi_potential": 0.3, "ceo_relevance": 0.25, "feasibility": 0.2, "speed_to_value": 0.15,
                 "competitive_moat": 0.1}
    assert sum(RubricWeights(3, 3, 2, 1, 1).as_dict().values()) == pytest.approx(1.0)


def test_weights_from_env(monkeypatch):
    monkeypatch.setenv("WEIGHT_CEO_RELEVANCE", "0.5")
    monkeypatch.setenv("WEIGHT_ROI", "0.5")
    for k in ("WEIGHT_FEASIBILITY", "WEIGHT_SPEED", "WEIGHT_MOAT"):
        monkeypatch.setenv(k, "0")
    w = load_settings().weights.as_dict()
    assert w["ceo_relevance"] == 0.5 and w["roi_potential"] == 0.5 and w["feasibility"] == 0


def test_older_scores_without_ceo_relevance_renormalize():
    s = OpportunityScore.model_validate({k: v for k, v in score("a", 8, 1).items() if k != "ceo_relevance"})
    # ceo_relevance missing: the other four weights (0.75 total) are renormalized
    expected = (8 * .3 + 7 * .2 + 7 * .15 + 6 * .1) / .75 * 10
    assert weighted_score(s, RubricWeights()) == pytest.approx(round(expected, 2))


# ------------------------------------------------------------------------------------------- confidence adjustment
def test_confidence_adjustment():
    assert adjusted_roi(10, 1.0) == 10 and adjusted_roi(10, 0.0) == 6 and adjusted_roi(9, 0.5) == 7.2
    assert adjusted_roi(9, None) == 9


def test_evidence_share_labels_and_unverified_public_data():
    s = OpportunityScore.model_validate(score("a", 8, 5, drivers=(
        ("public data", ["S1.F1"]), ("industry benchmark", []), ("assumption", []), ("public data", ["S9.F9"]))))
    assert evidence_share(s, {"S1.F1"}) == pytest.approx((1 + .5 + 0 + 0) / 4)   # S9.F9 doesn't exist
    assert evidence_share(s) == pytest.approx((1 + .5 + 0 + 1) / 4)              # ids not checked
    assert evidence_share(OpportunityScore.model_validate({**score("b", 8, 5), "value_drivers": []})) is None


# ------------------------------------------------------------------------------------------- Sobha regression
def test_sobha_assumption_heavy_non_core_idea_no_longer_wins():
    """The old Sobha run picked an EPC-review idea resting on assumed ROI over a core residential-sales idea."""
    opps, scores = build(
        [opp("opp-epc", "AI review of EPC contracts"), opp("opp-sales", "Site-visit-to-booking conversion")],
        [score("opp-epc", roi=9, ceo=3, drivers=(("assumption", []), ("assumption", []))),
         score("opp-sales", roi=7, ceo=9, drivers=(("public data", ["S2.F1"]), ("public data", ["S2.F3"])))])
    old = RubricWeights(roi_potential=.35, ceo_relevance=0, feasibility=.30, speed_to_value=.20, competitive_moat=.15)
    old_unadjusted = {s.opportunity_id: weighted_score(s, old) for s in scores.scores}
    assert old_unadjusted["opp-epc"] > old_unadjusted["opp-sales"]                  # the old behaviour
    ranked = rank_opportunities(opps, scores, RubricWeights(), {"S2.F1", "S2.F3"})
    assert ranked[0].opportunity_id == "opp-sales"
    epc = next(r for r in ranked if r.opportunity_id == "opp-epc")
    assert epc.evidence_share == 0 and epc.roi_adjusted == pytest.approx(5.4)


# ------------------------------------------------------------------------------------------- sensitivity
def test_sensitivity_flips_when_winner_is_fragile():
    opps, scores = build(
        [opp("opp-a", "Big bet", effort="high", low=20_000, high=100_000), opp("opp-b", "Safe bet")],
        [score("opp-a", roi=10, ceo=7), score("opp-b", roi=9, ceo=7)])
    ranked = rank_opportunities(opps, scores, RubricWeights(), {"S1.F1"})
    assert ranked[0].opportunity_id == "opp-a"
    sens = sensitivity(opps, ranked, RubricWeights())
    assert not sens.winner_stable and sens.conservative_winner_id == "opp-b"
    assert {(c.opportunity_id, c.base_rank, c.conservative_rank) for c in sens.rank_changes} == {
        ("opp-a", 1, 2), ("opp-b", 2, 1)}


def test_sensitivity_stable_when_winner_is_robust():
    opps, scores = build(
        [opp("opp-a", "Big bet", effort="low", low=90_000, high=100_000), opp("opp-b", "Safe bet")],
        [score("opp-a", roi=10, ceo=7), score("opp-b", roi=9, ceo=7)])
    ranked = rank_opportunities(opps, scores, RubricWeights(), {"S1.F1"})
    sens = sensitivity(opps, ranked, RubricWeights())
    assert sens.winner_stable and sens.rank_changes == []


# ------------------------------------------------------------------------------------------- pipeline
def test_pipeline_strategy_has_sensitivity_and_report_shows_why_not(tmp_path):
    llm = FakeLLM()
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    out = tmp_path / "maple-street-dental"
    strategy = WinningStrategy.model_validate_json((out / STRATEGY_JSON).read_text())
    assert strategy.sensitivity is not None and strategy.rubric_weights["ceo_relevance"] == 0.25
    assert "<stated_priorities>" in llm.prompts["EvaluationScores"]
    report = build_report(out)
    losers = [o for o in report.ai_opportunities if not o.is_recommended]
    assert losers and all(o.why_not for o in losers)
    md = render_report_markdown(report)
    assert "Sensitivity check" in md and "_Why not:" in md and "Evidence behind the value estimate" in md
