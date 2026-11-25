"""Assemble the 5-section assessment report from whatever stage outputs exist.

Pure Python, no LLM call. Works on complete runs, partial runs (e.g. only stage 1 finished),
and runs saved before the 5-section layout, so saved examples always open.

    1. Company Overview            <- 01_business_profile.json
    2. Key Business Information    <- 01_business_profile.json
    3. Potential Business Challenges (with reasoning) <- 02_business_challenges.json
                                      (fallback: the profile's operational bottlenecks)
    4. AI Opportunities            <- 03_ai_opportunities.json + 03_winning_strategy.json
    5. Personalized CEO Pitch      <- 04_ceo_pitch.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from agents.base import (
    CHALLENGES_JSON, META_JSON, VERIFY_JSON, OPPORTUNITIES_JSON, PITCH_JSON, PROFILE_JSON, PROTOTYPE_HTML, REPORT_JSON,
    REPORT_MD, STRATEGY_JSON, find_file,
)
from agents.builder import compute_roi, roi_headline
from utils.io import HandoffError, cell, write_json, write_text
from agents.trace import build_trace
from utils.schemas import (
    AIOpportunities, AssessmentReport, BusinessChallenge, BusinessChallenges, BusinessProfile, CEOPitch,
    CompanyOverview, ExecutivePitchDraft, KeyBusinessInformation, PitchOpening, ReportOpportunity, RubricScore, VerificationReport,
    WinningStrategy,
)

RUBRIC_LABELS = {
    "roi_potential": "ROI potential",
    "feasibility": "Feasibility",
    "speed_to_value": "Speed to value",
    "competitive_moat": "Competitive moat",
    "ceo_relevance": "CEO relevance",
}


def _load(path: Path | None, schema):
    if path is None:
        return None
    try:
        return schema.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, ValueError, OSError):
        return None


def _challenges_from_profile(profile: BusinessProfile) -> list[BusinessChallenge]:
    """Older runs have no stage-2 output; present the researcher's bottlenecks as challenges."""
    return [
        BusinessChallenge(
            id=f"ch-{i}", category="operational", title=b.area.capitalize(), description=b.description,
            reasoning=f"{b.evidence} (from the research stage; the dedicated challenge analysis has not run "
                      "for this company yet).",
            signals=[b.evidence], business_impact="Not yet assessed.", severity="medium", confidence=b.confidence,
        )
        for i, b in enumerate(profile.operational_bottlenecks, 1)
    ]


def build_report(out_dir: Path) -> AssessmentReport:
    profile = _load(find_file(out_dir, PROFILE_JSON), BusinessProfile)
    if profile is None:
        raise HandoffError(f"No valid {PROFILE_JSON} in {out_dir}; nothing to report yet.")
    stages = [1]

    challenges_doc = _load(find_file(out_dir, CHALLENGES_JSON), BusinessChallenges)
    if challenges_doc:
        stages.append(2)
        challenges = challenges_doc.challenges
    else:
        challenges = _challenges_from_profile(profile)

    opps = _load(find_file(out_dir, OPPORTUNITIES_JSON), AIOpportunities)
    strategy = _load(find_file(out_dir, STRATEGY_JSON), WinningStrategy)
    ranking = {r.opportunity_id: r for r in strategy.ranking} if strategy else {}
    opportunities: list[ReportOpportunity] = []
    why_not = {x.opportunity_id: x.reason for x in strategy.summary.why_not_the_others} if strategy else {}
    if opps:
        for o in opps.opportunities:
            r = ranking.get(o.id)
            opportunities.append(ReportOpportunity(
                id=o.id, rank=r.rank if r else None, title=o.title, category=o.category,
                problem_solved=o.problem_solved, addresses_challenges=o.addresses_challenges,
                applies_to=o.applies_to or o.why_this_business, ai_mechanism=o.ai_mechanism,
                expected_impact=o.estimated_impact.summary, primary_metric=o.estimated_impact.primary_metric,
                effort=f"{o.estimated_effort.level} · ~{o.estimated_effort.timeline_weeks} weeks · {o.estimated_effort.team}",
                weighted_score=r.weighted_score if r else None,
                rubric=[
                    RubricScore(criterion=c, label=label, score=getattr(r.scores, c).score,
                                weight=strategy.rubric_weights.get(c, 0.0), rationale=getattr(r.scores, c).rationale)
                    for c, label in RUBRIC_LABELS.items() if getattr(r.scores, c, None) is not None
                ] if r and strategy else [],
                evidence_share=r.evidence_share if r else None, roi_adjusted=r.roi_adjusted if r else None,
                why_not=why_not.get(o.id),
                build_vs_buy=o.build_vs_buy, pilot_30_60_90=o.pilot_30_60_90, data_readiness=o.data_readiness,
                compliance=o.compliance,
                biggest_risk=r.scores.biggest_risk if r else None,
                is_recommended=bool(strategy and strategy.winner.id == o.id),
            ))
        opportunities.sort(key=lambda x: (x.rank is None, x.rank or 0))
        if strategy:
            stages.append(3)

    pitch = None
    pitch_path = find_file(out_dir, PITCH_JSON)
    if pitch_path:
        try:
            raw = json.loads(pitch_path.read_text(encoding="utf-8"))
            draft = ExecutivePitchDraft.model_validate(raw.get("draft", raw))
            roi = compute_roi(draft) if draft.roi_line_items else None
            opening = raw.get("opening") if isinstance(raw, dict) and "draft" in raw else None
            opening = PitchOpening.model_validate(opening) if opening else None
            pitch = CEOPitch(
                addressed_to=draft.addressed_to or draft.recipient_role,
                title=draft.ceo_pitch_title or f"AI opportunities for {profile.business_name}",
                opening=opening, ceo_statements_found=bool(opening and opening.kind == "stated_priority"),
                why_we_reached_out=draft.why_we_reached_out or draft.elevator_pitch,
                opportunities_identified=draft.opportunities_identified,
                recommended_solutions=draft.recommended_solutions,
                roi_headline=roi_headline(roi) if roi else None,
                closing=draft.closing or draft.next_step_cta,
                short_version=draft.short_version,
                email_subject=draft.email_subject, email_body=draft.email_body,
                elevator_pitch=draft.elevator_pitch,
            )
            stages.append(4)
        except (ValidationError, ValueError, OSError):
            pitch = None

    verification = None
    vpath = out_dir / VERIFY_JSON
    if pitch is not None and vpath.exists():
        try:
            verification = VerificationReport.model_validate_json(vpath.read_text(encoding="utf-8"))
        except (ValidationError, ValueError, OSError):
            verification = None

    generated_at = None
    meta_path = out_dir / META_JSON
    if meta_path.exists():
        try:
            generated_at = json.loads(meta_path.read_text()).get("finished_at")
        except ValueError:
            pass
    if not generated_at:
        generated_at = datetime.fromtimestamp(
            find_file(out_dir, PROFILE_JSON).stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")

    report = AssessmentReport(
        business_name=profile.business_name,
        slug=out_dir.name,
        generated_at=generated_at,
        data_quality=profile.data_quality,
        stages_completed=stages,
        company_overview=CompanyOverview(
            name=profile.business_name, website=profile.website, what_they_do=profile.description,
            industry=profile.industry, sub_industry=profile.sub_industry, business_model=profile.business_model,
            headquarters=profile.headquarters, scale=profile.scale, company_size=profile.company_size_estimate,
            geographic_presence=profile.geographic_presence or ([profile.headquarters] if profile.headquarters else []),
            leadership=profile.leadership,
        ),
        key_business_information=KeyBusinessInformation(
            offerings=profile.core_products_services, major_projects=profile.major_projects,
            recent_developments=profile.recent_news, expansion_plans=profile.expansion_plans,
            public_information=profile.public_information, target_audience=profile.target_audience,
            competitors=profile.competitors,
        ),
        business_challenges=challenges,
        ai_opportunities=opportunities,
        sensitivity=strategy.sensitivity if strategy else None,
        recommended_opportunity_id=strategy.winner.id if strategy else None,
        ceo_pitch=pitch,
        verification=verification,
        prototype_available=(out_dir / PROTOTYPE_HTML).exists(),
        assumptions=profile.assumptions,
        sources=profile.sources,
    )
    report.citations, report.trace = build_trace(report, profile, challenges, opps, strategy)
    return report


# --------------------------------------------------------------------------- markdown
def _bullets(items: list[str], empty: str = "_Not found in public sources._") -> list[str]:
    return [f"- {i}" for i in items] if items else [empty]


def _marks(report: AssessmentReport, node_id: str) -> str:
    """Footnote markers for a rendered claim: ' [1][3]', or ' [no source]' for an uncited factual line."""
    if not report.trace:
        return ""
    node = next((n for n in report.trace.nodes if n.id == node_id), None)
    if node and node.citations:
        return " " + "".join(f"[{n}]" for n in node.citations)
    return " [no source]" if node_id in report.trace.uncited else ""


def _opening_lines(p: CEOPitch, report: AssessmentReport | None = None) -> list[str]:
    marks = _marks(report, "pitch-opening") if report and report.trace else f" [{p.opening.source_id}]" if p.opening else ""
    lines = [f"{p.opening.text}{marks}", ""] if p.opening else []
    if not p.ceo_statements_found:
        lines += ["_No CEO statements found in the sources read._", ""]
    return lines


def render_report_markdown(report: AssessmentReport) -> str:
    ov, kb = report.company_overview, report.key_business_information
    scale = ov.scale
    scale_lines = [f"- **{label}:** {value}" for label, value in (
        ("Revenue / bookings", scale.revenue), ("Projects / portfolio", scale.projects_or_portfolio),
        ("Employees", scale.employees or ov.company_size),
    ) if value] + [f"- {m}" for m in scale.other_metrics]

    lines = [
        f"# AI Opportunity Assessment — {report.business_name}",
        "",
        f"_Generated {report.generated_at or 'n/a'} · research data quality: **{report.data_quality}**"
        + (f" · {ov.website}" if ov.website else "") + "_",
        "",
        "## 1. Company Overview",
        "",
        ov.what_they_do,
        "",
        f"- **Industry:** {ov.industry}" + (f" — {ov.sub_industry}" if ov.sub_industry else ""),
        f"- **Business model:** {ov.business_model}",
        *( [f"- **Headquarters:** {ov.headquarters}"] if ov.headquarters else [] ),
        f"- **Geographic presence:** {', '.join(ov.geographic_presence) or 'Not found in public sources'}",
        *( [f"- **Leadership:** {'; '.join(ov.leadership)}"] if ov.leadership else [] ),
        "",
        "**Scale**",
        "",
        *(scale_lines or ["_Scale figures were not found in public sources._"]),
        "",
        "## 2. Key Business Information",
        "",
        "### Major offerings",
        "",
        *[f"- **{o.name}** — {o.description}" for o in kb.offerings],
        "",
    ]
    if kb.major_projects:
        lines += ["### Major projects", "", "| Project | Location | Segment | Status | Details |", "|---|---|---|---|---|"]
        lines += [f"| {cell(p.name)} | {cell(p.location or '—')} | {cell(p.segment or '—')} | {cell(p.status or '—')} "
                  f"| {cell(p.details or '—')} |" for p in kb.major_projects]
        lines.append("")
    lines += ["### Recent developments", ""]
    lines += [f"- **{n.headline}**" + (f" ({n.date})" if n.date else "") + f" — {n.summary}"
              for n in kb.recent_developments] or ["_None found._"]
    lines += ["", "### Expansion plans", "", *_bullets(kb.expansion_plans), ""]
    lines += ["### Important public information", ""]
    lines += [f"- **{i.category}:** {i.detail}" for i in kb.public_information] or ["_None found._"]
    lines += ["", "## 3. Potential Business Challenges", ""]
    labels = {"operational": "Operational", "sales": "Sales", "customer_experience": "Customer experience"}
    for c in report.business_challenges:
        lines += [
            f"### {c.id} · {c.title}{_marks(report, c.id)}",
            f"_{labels.get(c.category, c.category)} · severity {c.severity} · confidence {c.confidence}_",
            "",
            c.description,
            "",
            f"**Reasoning:** {c.reasoning}",
            "",
            "**Signals:** " + "; ".join(c.signals),
            "",
            f"**Business impact:** {c.business_impact}",
            "",
        ]
    lines += ["## 4. AI Opportunities", ""]
    if not report.ai_opportunities:
        lines += ["_This stage has not run yet for this company._", ""]
    for o in report.ai_opportunities:
        star = " ⭐ Recommended" if o.is_recommended else ""
        score = f" · score {o.weighted_score:.1f}/100" if o.weighted_score is not None else ""
        lines += [
            f"### {o.rank or '-'}. {o.title}{star}{_marks(report, o.id)}",
            f"_{o.category.replace('_', ' ')}{score} · solves {', '.join(o.addresses_challenges) or '—'}_",
            "",
            f"- **Applies to:** {o.applies_to}",
            f"- **Problem solved:** {o.problem_solved}",
            f"- **How the AI works:** {o.ai_mechanism}",
            f"- **Expected impact:** {o.expected_impact} (metric: {o.primary_metric})",
            f"- **Effort:** {o.effort}",
        ]
        if o.evidence_share is not None:
            lines.append(f"- **Evidence behind the value estimate:** {o.evidence_share:.0%} (ROI score adjusted to "
                         f"{o.roi_adjusted:g}/10)")
        if o.build_vs_buy:
            vendors = ", ".join(f"[{v.name}]({v.url})" for v in o.build_vs_buy.vendor_refs) or "no curated vendor fits"
            lines.append(f"- **Build vs buy:** {o.build_vs_buy.decision} · {vendors}. {o.build_vs_buy.rationale}")
        if o.pilot_30_60_90:
            lines.append("- **30/60/90-day pilot:** " + "; ".join(
                f"day {m.day}: {m.milestone} ({m.kpi}: {m.target})" for m in sorted(o.pilot_30_60_90, key=lambda m: m.day)))
        if o.data_readiness:
            lines.append("- **Data readiness:** " + "; ".join(f"{d.source}: {d.status}" for d in o.data_readiness))
        if o.compliance:
            lines.append("- **Compliance:** " + "; ".join(f"[{c.title}]({c.url}): {c.note}" for c in o.compliance))
        if o.why_not and not o.is_recommended:
            lines.append(f"- _Why not: {o.why_not}_")
        lines.append("")
    sens = report.sensitivity
    if sens:
        titles = {o.id: o.title for o in report.ai_opportunities}
        lines.append("**Sensitivity check (conservative case):** " + (
            "the recommended idea still wins." if sens.winner_stable else
            f"the winner would change to {titles.get(sens.conservative_winner_id, sens.conservative_winner_id)}."))
        lines += [f"- {c.title}: #{c.base_rank} → #{c.conservative_rank}" for c in sens.rank_changes] + [""]
    lines += ["## 5. Personalized CEO Pitch", ""]
    p = report.ceo_pitch
    if not p:
        lines += ["_This stage has not run yet for this company._", ""]
    else:
        lines += [f"**To:** {p.addressed_to}, {report.business_name}", "", f"### {p.title}", "",
                  "**Why we reached out**", "", *_opening_lines(p, report), _cited_paragraph(report, p), "",
                  "**Opportunities we identified**", ""]
        lines += [f"- **{o.title}** — {o.evidence}{_marks(report, f'pitch-opp-{i}')}"
                  for i, o in enumerate(p.opportunities_identified, 1)]
        lines += ["", "**What we recommend**", ""]
        for i, s in enumerate(p.recommended_solutions, 1):
            lines.append(f"{i}. **{s.name}** ({s.maps_to}) — {s.what_it_does} Impact: {s.expected_impact}. "
                         f"Timeline: {s.timeline}.")
        if p.roi_headline:
            lines += ["", f"**The numbers:** {p.roi_headline}."]
        lines += ["", p.closing, ""]
        v = report.verification
        if v and v.pass_rate is not None:
            lines += [f"**Verification:** {v.supported}/{v.checked} factual claims supported ({v.pass_rate:.0%}); "
                      f"{v.estimates} estimate(s) excluded. Details in 04_verification.json.", ""]
            lines += [f"- {a}" for a in v.actions] + ([""] if v.actions else [])
    if report.assumptions:
        lines += ["---", "", "### Assumptions", "", *_bullets(report.assumptions), ""]
    if report.citations:
        lines += ["### Sources", ""]
        lines += [f"{c.n}. [{c.title or c.url}]({c.url}) · {c.source_type or 'source'}"
                  + (f" · {c.date}" if c.date else "") + f" · `{c.source_id}`" for c in report.citations]
        lines.append("")
    elif report.sources:
        lines += ["### Sources", "", *_bullets(report.sources), ""]
    return "\n".join(lines)


def _cited_paragraph(report: AssessmentReport, p: CEOPitch) -> str:
    """'Why we reached out', sentence by sentence, each with its footnote markers."""
    if not report.trace:
        return p.why_we_reached_out
    lines = [n for n in report.trace.nodes if n.field == "why_we_reached_out"]
    return " ".join(f"{n.label}{_marks(report, n.id)}" for n in lines) or p.why_we_reached_out


def render_ceo_pitch_text(report: AssessmentReport) -> str:
    """Plain-text pitch for the Copy button and the 1-page view."""
    p = report.ceo_pitch
    if not p:
        return ""
    lines = [p.title, "", f"To: {p.addressed_to}, {report.business_name}", "", "Why we reached out", *[x for x in _opening_lines(p) if x], p.why_we_reached_out,
             "", "Opportunities we identified", *[f"• {o.title} — {o.evidence}" for o in p.opportunities_identified],
             "", "What we recommend"]
    lines += [f"{i}. {s.name} ({s.maps_to}): {s.what_it_does} Impact: {s.expected_impact}. Timeline: {s.timeline}."
              for i, s in enumerate(p.recommended_solutions, 1)]
    if p.roi_headline:
        lines += ["", f"The numbers: {p.roi_headline}."]
    lines += ["", p.closing, "", "[Your Name]"]
    return "\n".join(lines)


def write_report(out_dir: Path) -> list[Path]:
    report = build_report(out_dir)
    return [write_json(out_dir / REPORT_JSON, report), write_text(out_dir / REPORT_MD, render_report_markdown(report))]
