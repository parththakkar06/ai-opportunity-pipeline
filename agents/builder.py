"""Agent 4: Pitch & Prototype Builder -> 04_executive_pitch.md (+ .json) and 04_prototype.html"""
from __future__ import annotations

import html as html_lib
import re
from pathlib import Path

from agents.base import (
    CHALLENGES_JSON, PITCH_JSON, PITCH_MD, PROFILE_JSON, PROTOTYPE_HTML, STRATEGY_JSON, Agent, as_json,
)
from utils.io import cell, read_model, write_json, write_text
from utils.schemas import BusinessChallenges, BusinessProfile, ExecutivePitchDraft, ROISummary, WinningStrategy

TAILWIND_TAG = '<script src="https://cdn.tailwindcss.com"></script>'


# --------------------------------------------------------------------------- ROI math
def compute_roi(draft: ExecutivePitchDraft) -> ROISummary:
    value_low = sum(min(i.annual_value_usd_low, i.annual_value_usd_high) for i in draft.roi_line_items)
    value_high = sum(max(i.annual_value_usd_low, i.annual_value_usd_high) for i in draft.roi_line_items)
    cost_low = min(draft.implementation_cost_usd_low, draft.implementation_cost_usd_high)
    cost_high = max(draft.implementation_cost_usd_low, draft.implementation_cost_usd_high)
    running = max(0.0, draft.annual_running_cost_usd)
    net_low, net_high = value_low - running, value_high - running

    def payback(cost: float, net: float) -> float | None:
        return round(cost / (net / 12), 1) if net > 0 else None

    def roi3(cost: float, net: float) -> float | None:
        return round((3 * net - cost) / cost * 100, 0) if cost > 0 else None

    return ROISummary(
        annual_value_usd_low=round(value_low, 2),
        annual_value_usd_high=round(value_high, 2),
        net_annual_value_usd_low=round(net_low, 2),
        net_annual_value_usd_high=round(net_high, 2),
        payback_months_best=payback(cost_low, net_high),
        payback_months_worst=payback(cost_high, net_low),
        three_year_roi_pct_low=roi3(cost_high, net_low),     # conservative: high cost, low value
        three_year_roi_pct_high=roi3(cost_low, net_high),    # optimistic: low cost, high value
    )


def _usd(x: float) -> str:
    return f"${x:,.0f}"


def render_pitch_markdown(draft: ExecutivePitchDraft, roi: ROISummary, strategy: WinningStrategy,
                          profile: BusinessProfile) -> str:
    def months(x: float | None) -> str:
        return "not reached" if x is None else f"{x:.1f} months"

    def pct(x: float | None) -> str:
        return "n/a" if x is None else f"{x:,.0f}%"

    lines = [
        render_ceo_pitch_markdown(draft, profile, roi).rstrip(),
        "",
        "---",
        "",
        "# Appendix — outreach kit & ROI model",
        "",
        f"**Initiative:** {strategy.winner.title} · **For:** {draft.recipient_role}",
        "",
        "## 1. Cold outreach email",
        "",
        f"**Subject:** {draft.email_subject}",
        "",
        draft.email_body.strip(),
        "",
        "## 2. 60-second elevator pitch",
        "",
        draft.elevator_pitch.strip(),
        "",
        "## 3. ROI breakdown",
        "",
        "| Headline | Conservative | Optimistic |",
        "|---|---:|---:|",
        f"| Annual value created | {_usd(roi.annual_value_usd_low)} | {_usd(roi.annual_value_usd_high)} |",
        f"| Annual running cost | {_usd(draft.annual_running_cost_usd)} | {_usd(draft.annual_running_cost_usd)} |",
        f"| Net annual value | {_usd(roi.net_annual_value_usd_low)} | {_usd(roi.net_annual_value_usd_high)} |",
        f"| One-time implementation | {_usd(max(draft.implementation_cost_usd_low, draft.implementation_cost_usd_high))} "
        f"| {_usd(min(draft.implementation_cost_usd_low, draft.implementation_cost_usd_high))} |",
        f"| Payback period | {months(roi.payback_months_worst)} | {months(roi.payback_months_best)} |",
        f"| 3-year ROI | {pct(roi.three_year_roi_pct_low)} | {pct(roi.three_year_roi_pct_high)} |",
        "",
        "### Value drivers",
        "",
        "| Driver | Calculation | Low / yr | High / yr |",
        "|---|---|---:|---:|",
        *[f"| {cell(i.item)} | {cell(i.calculation)} | {_usd(i.annual_value_usd_low)} | {_usd(i.annual_value_usd_high)} |"
          for i in draft.roi_line_items],
        "",
        "### Assumptions",
        "",
        "| Assumption | Value | Source |",
        "|---|---|---|",
        *[f"| {cell(a.label)} | {cell(a.value)} | {a.source} |" for a in draft.roi_assumptions],
        "",
        "### Caveats",
        "",
        *[f"- {c}" for c in draft.caveats],
    ]
    if profile.data_quality == "low":
        lines.append("- Public information on this business was limited; treat all figures as illustrative "
                     "until validated with real data in the pilot.")
    lines += [
        "",
        "_Totals, payback and ROI are computed from the line items above; conservative = low value with high cost._",
        "",
        "## Next step",
        "",
        draft.next_step_cta,
        "",
    ]
    return "\n".join(lines)


def roi_headline(roi: ROISummary) -> str | None:
    if roi.annual_value_usd_high <= 0:
        return None
    text = f"{_usd(roi.annual_value_usd_low)}–{_usd(roi.annual_value_usd_high)} estimated annual value"
    if roi.payback_months_worst is not None:
        text += f", payback in about {roi.payback_months_worst:.0f} months or less"
    return text


def render_ceo_pitch_markdown(draft: ExecutivePitchDraft, profile: BusinessProfile, roi: ROISummary | None) -> str:
    """The one-page pitch to the CEO: (a) why we reached out, (b) opportunities, (c) solutions."""
    addressed = draft.addressed_to or draft.recipient_role
    title = draft.ceo_pitch_title or f"AI opportunities for {profile.business_name}"
    lines = [
        f"# {title}",
        "",
        f"**To:** {addressed}, {profile.business_name}",
        "",
        "## Why we reached out",
        "",
        (draft.why_we_reached_out or draft.elevator_pitch).strip(),
        "",
        "## Opportunities we identified",
        "",
        *[f"- **{o.title}** — {o.evidence}" for o in draft.opportunities_identified],
        "",
        "## What we recommend",
        "",
    ]
    for i, sol in enumerate(draft.recommended_solutions, 1):
        lines += [
            f"**{i}. {sol.name}** _({sol.maps_to})_  ",
            f"{sol.what_it_does}  ",
            f"Impact: {sol.expected_impact} · Timeline: {sol.timeline}",
            "",
        ]
    headline = roi_headline(roi) if roi else None
    if headline:
        lines += [f"**The numbers:** {headline} (assumptions in the appendix).", ""]
    lines += [(draft.closing or draft.next_step_cta).strip(), "", "[Your Name]", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- prototype HTML
def finalize_prototype_html(raw: str, title: str) -> tuple[str, list[str]]:
    """Make the model's HTML safe to save: strip fences, ensure a full document and Tailwind."""
    notes: list[str] = []
    text = raw.strip()
    fence = re.search(r"```(?:html)?\s*(.*?)```", text, re.S | re.I)
    if fence and "<" in fence.group(1):
        text = fence.group(1).strip()
        notes.append("removed markdown code fences")
    start = re.search(r"<!doctype html|<html", text, re.I)
    if start and start.start() > 0:
        text = text[start.start():]
        notes.append("removed text before the HTML document")
    end = text.lower().rfind("</html>")
    if end != -1:
        text = text[: end + len("</html>")]

    if not re.search(r"<html", text, re.I):
        notes.append("model returned a fragment; wrapped it in a full HTML document")
        text = (
            "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{html_lib.escape(title)}</title>\n{TAILWIND_TAG}\n</head>\n"
            f"<body class=\"bg-slate-50\">\n{text}\n</body>\n</html>\n"
        )
    if not re.search(r"<!doctype html", text, re.I):
        text = "<!DOCTYPE html>\n" + text
    if "cdn.tailwindcss.com" not in text:
        notes.append("added the Tailwind CDN script")
        if re.search(r"<head[^>]*>", text, re.I):
            text = re.sub(r"(<head[^>]*>)", r"\1\n" + TAILWIND_TAG, text, count=1, flags=re.I)
        else:
            text = re.sub(r"(<html[^>]*>)", r"\1\n<head>" + TAILWIND_TAG + "</head>", text, count=1, flags=re.I)
    if not re.search(r"</html>\s*$", text, re.I):
        notes.append("output looked truncated; closed open body/html tags")
        if "</body>" not in text.lower():
            text += "\n</body>"
        text += "\n</html>\n"
    return text, notes


def looks_complete(raw: str) -> bool:
    lowered = raw.lower()
    return "</html>" in lowered and "<script" in lowered and "<body" in lowered


class BuilderAgent(Agent):
    stage = 4
    key = "builder"
    title = "CEO Pitch Builder"

    def run(self) -> list[Path]:
        ctx = self.ctx
        profile = read_model(ctx.path(PROFILE_JSON), BusinessProfile)
        strategy = read_model(ctx.path(STRATEGY_JSON), WinningStrategy)
        challenges = read_model(ctx.path(CHALLENGES_JSON), BusinessChallenges)
        shared = (
            f"<business_profile>\n{as_json(profile)}\n</business_profile>\n\n"
            f"<business_challenges>\n{as_json(challenges)}\n</business_challenges>\n\n"
            f"<ranked_opportunities>\n{as_json([r.model_dump(exclude={'scores'}) for r in strategy.ranking])}\n"
            "</ranked_opportunities>\n\n"
            f"<winning_strategy>\n{as_json(strategy.model_dump(exclude={'ranking'}))}\n</winning_strategy>\n\n"
        )

        # ---- pitch
        ctx.status("writing the one-page CEO pitch, outreach email and ROI model…")

        def check_pitch(d: ExecutivePitchDraft) -> str | None:
            if not d.why_we_reached_out.strip():
                return "why_we_reached_out is empty; ground it in specific recent facts about the company."
            if len(d.opportunities_identified) < 2:
                return "opportunities_identified needs 3-4 items, each with evidence."
            if len(d.recommended_solutions) < 2:
                return "recommended_solutions needs 2-4 concrete AI solutions, the top-ranked strategy first."
            if not d.roi_line_items:
                return "roi_line_items is empty; provide 2-5 value drivers."
            if len(d.email_body.split()) > 230:
                return f"email_body is {len(d.email_body.split())} words; keep it under 180."
            return None

        draft = ctx.llm.structured(
            agent=self.key, system=self.prompt("builder_pitch.md"),
            user=shared + "Write the one-page CEO pitch and the supporting outreach kit.", schema=ExecutivePitchDraft,
            model=ctx.settings.builder_model, effort=ctx.settings.effort, check=check_pitch,
        )
        roi = compute_roi(draft)
        pitch_md = render_pitch_markdown(draft, roi, strategy, profile)
        files = [
            write_text(ctx.path(PITCH_MD), pitch_md),
            write_json(ctx.path(PITCH_JSON), {"draft": draft.model_dump(mode="json"),
                                             "roi": roi.model_dump(mode="json")}),
        ]

        # ---- prototype (optional: BUILD_PROTOTYPE=false or the API's include_prototype=false)
        if not ctx.settings.build_prototype:
            ctx.note("prototype skipped (BUILD_PROTOTYPE=false)")
            return files
        ctx.status("building the interactive prototype (the longest step)…")
        user = shared + (
            f"Build the interactive prototype for \"{strategy.winner.title}\" at {profile.business_name}. "
            f"Brand primary color: {profile.brand.primary_color_hex or 'unknown — choose one that fits'}. "
            f"Tone: {profile.brand.tone_of_voice}."
        )
        result = ctx.llm.text(agent=self.key, system=self.prompt("builder_prototype.md"), user=user,
                              model=ctx.settings.builder_model, effort=ctx.settings.builder_effort)
        if result.truncated or not looks_complete(result.text):
            ctx.note("first prototype draft was incomplete; asking for a more compact version")
            retry = ctx.llm.text(
                agent=self.key, system=self.prompt("builder_prototype.md"),
                user=user + "\n\nYour previous attempt was cut off. Produce a more compact version "
                            "(under ~600 lines) that is still fully interactive.",
                model=ctx.settings.builder_model, effort=ctx.settings.builder_effort)
            if looks_complete(retry.text) or len(retry.text) > len(result.text):
                result = retry

        html, notes = finalize_prototype_html(result.text, f"{profile.business_name} · {strategy.winner.title}")
        for n in notes:
            ctx.note(f"prototype: {n}")
        files.append(write_text(ctx.path(PROTOTYPE_HTML), html))
        return files
