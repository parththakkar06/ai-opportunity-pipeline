"""Agent 3: Executive Evaluator -> 03_winning_strategy.json + 03_winning_strategy.md

The LLM scores each criterion 1-10 with a rationale. Python computes the weighted
totals and picks the winner, so the ranking is deterministic and auditable.
"""
from __future__ import annotations

from pathlib import Path

from agents.base import (
    OPPORTUNITIES_JSON, PROFILE_JSON, STRATEGY_JSON, STRATEGY_MD, Agent, as_json, facts_digest, profile_for_prompt,
)
from utils.config import RubricWeights
from utils.io import cell, read_model, write_json, write_text
from utils.schemas import (
    AIOpportunities,
    BusinessProfile,
    EvaluationScores,
    ExecutiveSummary,
    OpportunityScore,
    RankChange,
    RankedOpportunity,
    Sensitivity,
    WinningStrategy,
)

CRITERIA = ("roi_potential", "ceo_relevance", "feasibility", "speed_to_value", "competitive_moat")
CRITERION_LABELS = {
    "roi_potential": "ROI Potential",
    "ceo_relevance": "CEO Relevance",
    "feasibility": "Feasibility",
    "speed_to_value": "Speed-to-Value",
    "competitive_moat": "Competitive Moat",
}
SOURCE_WEIGHT = {"public data": 1.0, "industry benchmark": 0.5, "assumption": 0.0}


def clamp_scores(score: OpportunityScore) -> OpportunityScore:
    for c in CRITERIA:
        cs = getattr(score, c)
        if cs is not None:
            cs.score = max(1, min(10, int(cs.score)))
    return score


def evidence_share(score: OpportunityScore, fact_ids: set[str] | None = None) -> float | None:
    """Share of the value estimate that rests on evidence: public data 1, benchmark 0.5, assumption 0.

    A driver labelled 'public data' only counts if it cites a fact id that exists (when ids are given);
    otherwise it is treated as an assumption. None when the scorer gave no drivers (older runs)."""
    if not score.value_drivers:
        return None
    total = 0.0
    for d in score.value_drivers:
        src = d.source
        if src == "public data" and fact_ids is not None and not any(i in fact_ids for i in d.evidence):
            src = "assumption"
        total += SOURCE_WEIGHT[src]
    return round(total / len(score.value_drivers), 3)


def adjusted_roi(roi: float, share: float | None) -> float:
    """adj = roi × (0.6 + 0.4 × evidence_share). Without drivers the score is left as is."""
    return roi if share is None else round(roi * (0.6 + 0.4 * share), 2)


def weighted_score(score: OpportunityScore, weights: RubricWeights, roi: float | None = None,
                   feasibility: float | None = None) -> float:
    """0-100. Criteria the scorer didn't return (e.g. ceo_relevance in older runs) are left out and the
    remaining weights renormalized."""
    w = weights.as_dict()
    values = {c: getattr(score, c).score for c in CRITERIA if getattr(score, c) is not None}
    if roi is not None:
        values["roi_potential"] = roi
    if feasibility is not None:
        values["feasibility"] = feasibility
    total_w = sum(w[c] for c in values)
    return round(sum(values[c] * w[c] for c in values) / total_w * 10, 2) if total_w else 0.0


def rank_opportunities(opps: AIOpportunities, scores: EvaluationScores, weights: RubricWeights,
                       fact_ids: set[str] | None = None) -> list[RankedOpportunity]:
    by_id = {s.opportunity_id: clamp_scores(s) for s in scores.scores}
    rows = []
    for o in opps.opportunities:
        s = by_id[o.id]
        share = evidence_share(s, fact_ids)
        roi = adjusted_roi(s.roi_potential.score, share)
        rows.append((weighted_score(s, weights, roi=roi), roi, s.feasibility.score, o, s, share))
    # Ties break on adjusted ROI, then feasibility, then original order (stable sort).
    rows.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    return [
        RankedOpportunity(rank=i, opportunity_id=o.id, title=o.title, weighted_score=ws, scores=s,
                          evidence_share=share, roi_adjusted=roi)
        for i, (ws, roi, _, o, s, share) in enumerate(rows, 1)
    ]


def sensitivity(opps: AIOpportunities, ranking: list[RankedOpportunity], weights: RubricWeights) -> Sensitivity:
    """Re-rank under conservative settings and report whether the winner survives.

    - value: ROI scaled by the low/high ratio of the value estimate (floor 0.5)
    - confidence: the evidence shrink applied a second time
    - feasibility: -1 for high-effort ideas
    """
    by_id = {o.id: o for o in opps.opportunities}
    scored = []
    for r in ranking:
        o = by_id[r.opportunity_id]
        lo, hi = o.estimated_impact.annual_value_usd_low, o.estimated_impact.annual_value_usd_high
        ratio = max(0.5, min(1.0, lo / hi)) if lo and hi and hi > 0 else 0.75
        roi = adjusted_roi(r.roi_adjusted if r.roi_adjusted is not None else r.scores.roi_potential.score,
                           r.evidence_share if r.evidence_share is not None else 0.5) * ratio
        feas = max(1, r.scores.feasibility.score - (1 if o.estimated_effort.level == "high" else 0))
        scored.append((weighted_score(r.scores, weights, roi=roi, feasibility=feas), roi, r))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    new_rank = {r.opportunity_id: i for i, (_, _, r) in enumerate(scored, 1)}
    changes = [RankChange(opportunity_id=r.opportunity_id, title=r.title, base_rank=r.rank,
                          conservative_rank=new_rank[r.opportunity_id])
               for r in ranking if new_rank[r.opportunity_id] != r.rank]
    return Sensitivity(winner_stable=scored[0][2].opportunity_id == ranking[0].opportunity_id,
                       conservative_winner_id=scored[0][2].opportunity_id,
                       conservative_scores={r.opportunity_id: round(ws, 2) for ws, _, r in scored},
                       rank_changes=changes)


def titles_of(strategy: WinningStrategy) -> dict[str, str]:
    return {r.opportunity_id: r.title for r in strategy.ranking}


def render_strategy_markdown(strategy: WinningStrategy, profile: BusinessProfile) -> str:
    w, s, winner = strategy.rubric_weights, strategy.summary, strategy.winner
    lines = [
        f"# Winning AI Strategy — {strategy.business_name}",
        "",
        f"> **{s.headline}**",
        "",
        f"**Winner:** {winner.title} · weighted score **{strategy.winner_weighted_score:.1f}/100**  ",
        f"**Category:** {winner.category.replace('_', ' ')} · **Effort:** {winner.estimated_effort.level}, "
        f"~{winner.estimated_effort.timeline_weeks} weeks · **Data quality of research:** {profile.data_quality}",
        "",
        "## Executive summary",
        "",
        s.executive_summary,
        "",
        "## Why it wins",
        "",
        *[f"- {b}" for b in s.why_it_wins],
        "",
        "## Scoreboard",
        "",
        "Weights: " + ", ".join(f"{CRITERION_LABELS[c]} {w[c] * 100:.0f}%" for c in CRITERIA if c in w),
        "ROI is confidence-adjusted: ROI × (0.6 + 0.4 × evidence share).",
        "",
        "| Rank | Opportunity | ROI (adj.) | Evidence | CEO | Feas. | Speed | Moat | Weighted |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in strategy.ranking:
        sc = r.scores
        roi = f"{sc.roi_potential.score}" + (f" ({r.roi_adjusted:g})" if r.roi_adjusted is not None else "")
        share = f"{r.evidence_share:.0%}" if r.evidence_share is not None else "—"
        ceo = sc.ceo_relevance.score if sc.ceo_relevance else "—"
        lines.append(
            f"| {r.rank} | {cell(r.title)} | {roi} | {share} | {ceo} | {sc.feasibility.score} | "
            f"{sc.speed_to_value.score} | {sc.competitive_moat.score} | **{r.weighted_score:.1f}** |"
        )
    sens = strategy.sensitivity
    if sens:
        lines += ["", "**Sensitivity (conservative case):** " + (
            "the winner holds." if sens.winner_stable else
            f"the winner changes to {titles_of(strategy).get(sens.conservative_winner_id, sens.conservative_winner_id)}.")]
        lines += [f"- {c.title}: #{c.base_rank} → #{c.conservative_rank}" for c in sens.rank_changes]
    titles = {r.opportunity_id: r.title for r in strategy.ranking}
    lines += ["", "## Why not the others", ""]
    lines += [f"- **{titles.get(x.opportunity_id, x.opportunity_id)}** — {x.reason}" for x in s.why_not_the_others]
    lines += [
        "", "## The winning idea", "",
        f"**Problem:** {winner.problem_solved}", "",
        f"**How the AI works:** {winner.ai_mechanism}", "",
        f"**Why this business:** {winner.why_this_business}", "",
        f"**Expected impact:** {winner.estimated_impact.summary} ({winner.estimated_impact.basis})", "",
        "**Data required:** " + "; ".join(winner.required_data), "",
        "## Implementation plan", "",
    ]
    for i, p in enumerate(s.implementation_phases, 1):
        lines.append(f"{i}. **{p.name}** ({p.duration_weeks} wk) — " + "; ".join(p.deliverables))
    lines += ["", "## Success metrics", "", *[f"- {m}" for m in s.success_metrics]]
    lines += ["", "## Risks & mitigations", "", "| Risk | Mitigation |", "|---|---|"]
    lines += [f"| {cell(r.risk)} | {cell(r.mitigation)} |" for r in s.risks_and_mitigations]
    lines += ["", "## Rubric rationale (winner)", ""]
    ws = strategy.ranking[0].scores
    lines += [f"- **{CRITERION_LABELS[c]} ({getattr(ws, c).score}/10):** {getattr(ws, c).rationale}"
              for c in CRITERIA if getattr(ws, c) is not None]
    lines.append("")
    return "\n".join(lines)


class EvaluatorAgent(Agent):
    stage = 3
    key = "evaluator"
    title = "Executive Evaluator"

    def run(self) -> list[Path]:
        ctx = self.ctx
        profile = read_model(ctx.path(PROFILE_JSON), BusinessProfile)
        opps = read_model(ctx.path(OPPORTUNITIES_JSON), AIOpportunities)
        expected_ids = {o.id for o in opps.opportunities}
        fact_ids = {f.fact_id for f in profile.facts}
        weights = ctx.settings.weights

        def check_scores(result: EvaluationScores) -> str | None:
            got = [s.opportunity_id for s in result.scores]
            missing, extra = expected_ids - set(got), set(got) - expected_ids
            dupes = {i for i in got if got.count(i) > 1}
            problems = []
            if missing:
                problems.append(f"Missing scores for: {sorted(missing)}.")
            if extra:
                problems.append(f"Unknown opportunity ids: {sorted(extra)}. Use only {sorted(expected_ids)}.")
            if dupes:
                problems.append(f"Scored more than once: {sorted(dupes)}.")
            for sc in result.scores:
                if sc.ceo_relevance is None:
                    problems.append(f"{sc.opportunity_id}: ceo_relevance is required.")
                if not sc.value_drivers:
                    problems.append(f"{sc.opportunity_id}: list 2-4 value_drivers with their source.")
            return " ".join(problems) or None

        ctx.status("scoring opportunities against the rubric…")
        scores = ctx.llm.structured(
            agent=self.key, system=self.prompt("evaluator.md"),
            user=(f"<business_profile>\n{as_json(profile_for_prompt(profile))}\n</business_profile>\n\n"
                  + (f"<stated_priorities>\n{as_json(profile.stated_priorities)}\n</stated_priorities>\n\n"
                     if profile.stated_priorities else
                     "<stated_priorities>none verified; judge ceo_relevance on fit with the core business"
                     "</stated_priorities>\n\n")
                  + (f"<evidence_facts>\n{facts_digest(profile)}\n</evidence_facts>\n\n" if profile.facts else "")
                  + f"<opportunities>\n{as_json(opps)}\n</opportunities>\n\nScore every opportunity."),
            schema=EvaluationScores, model=ctx.settings.model, effort=ctx.settings.builder_effort,
            check=check_scores,
        )

        ranking = rank_opportunities(opps, scores, weights, fact_ids if profile.facts else None)
        sens = sensitivity(opps, ranking, weights)
        winner_row = ranking[0]
        winner = next(o for o in opps.opportunities if o.id == winner_row.opportunity_id)
        ctx.note(f"winner: {winner.title} ({winner_row.weighted_score:.1f}/100)")
        ctx.note("sensitivity: winner " + ("holds in the conservative case" if sens.winner_stable else
                 f"changes to {sens.conservative_winner_id} in the conservative case"))

        others = {r.opportunity_id for r in ranking[1:]}

        def check_summary(result: ExecutiveSummary) -> str | None:
            covered = {r.opportunity_id for r in result.why_not_the_others}
            if others - covered:
                return f"why_not_the_others must include every non-winning id; missing {sorted(others - covered)}."
            return None

        ranking_table = "\n".join(
            f"{r.rank}. {r.opportunity_id} — {r.title}: {r.weighted_score:.1f}/100 "
            f"(ROI {r.scores.roi_potential.score}, Feasibility {r.scores.feasibility.score}, "
            f"Speed {r.scores.speed_to_value.score}, Moat {r.scores.competitive_moat.score}, "
            f"CEO relevance {r.scores.ceo_relevance.score if r.scores.ceo_relevance else 'n/a'}, "
            f"evidence share {r.evidence_share if r.evidence_share is not None else 'n/a'})"
            for r in ranking
        )
        ctx.status("writing the executive decision memo…")
        summary = ctx.llm.structured(
            agent=self.key, system=self.prompt("evaluator_summary.md"),
            user=(f"<business_profile>\n{as_json(profile_for_prompt(profile))}\n</business_profile>\n\n"
                  f"<rubric_weights>\n{as_json(weights.as_dict())}\n</rubric_weights>\n\n"
                  f"<ranking>\n{ranking_table}\n</ranking>\n\n"
                  f"<all_scores>\n{as_json([r.scores for r in ranking])}\n</all_scores>\n\n"
                  f"<winning_opportunity>\n{as_json(winner)}\n</winning_opportunity>\n\n"
                  f"<other_opportunities>\n{as_json([o for o in opps.opportunities if o.id != winner.id])}\n"
                  "</other_opportunities>\n\nWrite the executive decision memo."),
            schema=ExecutiveSummary, model=ctx.settings.model, effort=ctx.settings.effort,
            check=check_summary,
        )

        strategy = WinningStrategy(
            business_name=profile.business_name,
            rubric_weights=weights.as_dict(),
            ranking=ranking,
            winner=winner,
            winner_weighted_score=winner_row.weighted_score,
            summary=summary,
            sensitivity=sens,
        )
        return [
            write_json(ctx.path(STRATEGY_JSON), strategy),
            write_text(ctx.path(STRATEGY_MD), render_strategy_markdown(strategy, profile)),
        ]
