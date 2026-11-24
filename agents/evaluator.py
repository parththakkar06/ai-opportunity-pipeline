"""Agent 3: Executive Evaluator -> 03_winning_strategy.json + 03_winning_strategy.md

The LLM scores each criterion 1-10 with a rationale. Python computes the weighted
totals and picks the winner, so the ranking is deterministic and auditable.
"""
from __future__ import annotations

from pathlib import Path

from agents.base import OPPORTUNITIES_JSON, PROFILE_JSON, STRATEGY_JSON, STRATEGY_MD, Agent, as_json
from utils.config import RubricWeights
from utils.io import cell, read_model, write_json, write_text
from utils.schemas import (
    AIOpportunities,
    BusinessProfile,
    EvaluationScores,
    ExecutiveSummary,
    OpportunityScore,
    RankedOpportunity,
    WinningStrategy,
)

CRITERIA = ("roi_potential", "feasibility", "speed_to_value", "competitive_moat")
CRITERION_LABELS = {
    "roi_potential": "ROI Potential",
    "feasibility": "Feasibility",
    "speed_to_value": "Speed-to-Value",
    "competitive_moat": "Competitive Moat",
}


def clamp_scores(score: OpportunityScore) -> OpportunityScore:
    for c in CRITERIA:
        cs = getattr(score, c)
        cs.score = max(1, min(10, int(cs.score)))
    return score


def weighted_score(score: OpportunityScore, weights: RubricWeights) -> float:
    """0-100 scale."""
    w = weights.normalized()
    total = sum(getattr(score, c).score * getattr(w, c) for c in CRITERIA)
    return round(total * 10, 2)


def rank_opportunities(opps: AIOpportunities, scores: EvaluationScores,
                       weights: RubricWeights) -> list[RankedOpportunity]:
    by_id = {s.opportunity_id: clamp_scores(s) for s in scores.scores}
    rows = []
    for o in opps.opportunities:
        s = by_id[o.id]
        rows.append((weighted_score(s, weights), s.roi_potential.score, s.feasibility.score, o, s))
    # Ties break on ROI, then feasibility, then original order (stable sort).
    rows.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    return [
        RankedOpportunity(rank=i, opportunity_id=o.id, title=o.title, weighted_score=ws, scores=s)
        for i, (ws, _, _, o, s) in enumerate(rows, 1)
    ]


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
        "Weights: " + ", ".join(f"{CRITERION_LABELS[c]} {w[c] * 100:.0f}%" for c in CRITERIA),
        "",
        "| Rank | Opportunity | ROI | Feas. | Speed | Moat | Weighted |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for r in strategy.ranking:
        sc = r.scores
        lines.append(
            f"| {r.rank} | {cell(r.title)} | {sc.roi_potential.score} | {sc.feasibility.score} | "
            f"{sc.speed_to_value.score} | {sc.competitive_moat.score} | **{r.weighted_score:.1f}** |"
        )
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
    lines += [f"- **{CRITERION_LABELS[c]} ({getattr(ws, c).score}/10):** {getattr(ws, c).rationale}" for c in CRITERIA]
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
            return " ".join(problems) or None

        ctx.status("scoring opportunities against the rubric…")
        scores = ctx.llm.structured(
            agent=self.key, system=self.prompt("evaluator.md"),
            user=(f"<business_profile>\n{as_json(profile)}\n</business_profile>\n\n"
                  f"<opportunities>\n{as_json(opps)}\n</opportunities>\n\nScore every opportunity."),
            schema=EvaluationScores, model=ctx.settings.model, effort=ctx.settings.builder_effort,
            check=check_scores,
        )

        ranking = rank_opportunities(opps, scores, weights)
        winner_row = ranking[0]
        winner = next(o for o in opps.opportunities if o.id == winner_row.opportunity_id)
        ctx.note(f"winner: {winner.title} ({winner_row.weighted_score:.1f}/100)")

        others = {r.opportunity_id for r in ranking[1:]}

        def check_summary(result: ExecutiveSummary) -> str | None:
            covered = {r.opportunity_id for r in result.why_not_the_others}
            if others - covered:
                return f"why_not_the_others must include every non-winning id; missing {sorted(others - covered)}."
            return None

        ranking_table = "\n".join(
            f"{r.rank}. {r.opportunity_id} — {r.title}: {r.weighted_score:.1f}/100 "
            f"(ROI {r.scores.roi_potential.score}, Feasibility {r.scores.feasibility.score}, "
            f"Speed {r.scores.speed_to_value.score}, Moat {r.scores.competitive_moat.score})"
            for r in ranking
        )
        ctx.status("writing the executive decision memo…")
        summary = ctx.llm.structured(
            agent=self.key, system=self.prompt("evaluator_summary.md"),
            user=(f"<business_profile>\n{as_json(profile)}\n</business_profile>\n\n"
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
        )
        return [
            write_json(ctx.path(STRATEGY_JSON), strategy),
            write_text(ctx.path(STRATEGY_MD), render_strategy_markdown(strategy, profile)),
        ]
