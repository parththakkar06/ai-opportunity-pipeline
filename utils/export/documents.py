"""Exports built from a saved run, with no LLM calls: one-page pitch PDF, full report PDF, pitch deck,
email draft (.eml with the pitch attached, Gmail and mailto links) and a zip of everything."""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from urllib.parse import quote, urlencode

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Inches, Pt

from utils.export.data import ExportData, usd
from utils.export.pdf import html_to_pdf, page_count

TEMPLATES = Path(__file__).resolve().parent / "templates"
ENV = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["j2", "html"]))
MAILTO_LIMIT = 1800
MAX_BULLETS = 6
FILES = {"pptx": "06_pitch_deck.pptx", "report.pdf": "06_report.pdf", "pitch.pdf": "06_pitch_onepage.pdf",
         "eml": "06_outreach.eml"}


def _date(d: ExportData) -> str:
    raw = d.report.generated_at
    try:
        return datetime.fromisoformat(raw).strftime("%-d %B %Y") if raw else date.today().strftime("%-d %B %Y")
    except ValueError:
        return raw or ""


# ------------------------------------------------------------------------------------------- PDFs
def pitch_html(d: ExportData, short: bool = False, font_pt: float = 10.5, margin: str = "16mm") -> str:
    p = d.report.ceo_pitch
    if p is None:
        raise ValueError("This run has no CEO pitch yet.")
    uncited = set(d.report.trace.uncited) if d.report.trace else set()
    opp_marks = [d.marks(f"pitch-opp-{i}") for i in range(1, len(p.opportunities_identified) + 1)]
    why = [] if short else d.lines("why_we_reached_out")
    used = {n for nums in [d.marks("pitch-opening"), *opp_marks, *(x[1] for x in why)]
            for n in nums}
    return ENV.get_template("pitch.html.j2").render(
        r=d.report, p=p, accent=d.accent, short=short, font_pt=font_pt, margin=margin,
        opening_marks=d.marks("pitch-opening"), why=why,
        opp_marks=opp_marks, uncited=[f"pitch-opp-{i}" in uncited for i in range(1, len(opp_marks) + 1)],
        sources=[c for c in d.report.citations if c.n in used])


def pitch_pdf(d: ExportData) -> tuple[bytes, dict]:
    """Exactly one A4 page. Tries full text at 10.5pt, then the short version, then 10pt with tighter margins.
    Body text never goes below 10pt."""
    attempts = [dict(short=False, font_pt=10.5), dict(short=True, font_pt=10.5),
                dict(short=True, font_pt=10, margin="12mm"),
                dict(short=True, font_pt=10, margin="10mm")]
    for opts in attempts:
        pdf, engine = html_to_pdf(pitch_html(d, **opts))
        if page_count(pdf) == 1:
            return pdf, {**opts, "engine": engine}
    raise ValueError("The pitch doesn't fit on one page even in its short version at 10pt.")


def report_html(d: ExportData) -> str:
    r = d.report
    marks = {n.id: n.citations for n in r.trace.nodes} if r.trace else {}
    marks = _Marks(marks)
    winner = next((o for o in r.ai_opportunities if o.is_recommended), None)
    return ENV.get_template("report.html.j2").render(
        r=r, ov=r.company_overview, ki=r.key_business_information, p=r.ceo_pitch, v=r.verification,
        marks=marks, why=d.lines("why_we_reached_out"), winner=winner, accent=d.accent, font_pt=10,
        margin="18mm 16mm 20mm", date=_date(d))


class _Marks(dict):
    def __missing__(self, key):
        return []


def report_pdf(d: ExportData) -> tuple[bytes, str]:
    return html_to_pdf(report_html(d), page_numbers=True)


# ------------------------------------------------------------------------------------------- deck
def _rgb(hex_: str) -> RGBColor:
    return RGBColor.from_string(hex_.lstrip("#").upper())


def _clip(text: str, n: int = 150) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def deck_outline(d: ExportData) -> list[dict]:
    """The 10 slides as data: title, bullets (≤6), optional table, speaker notes."""
    r, p = d.report, d.report.ceo_pitch
    ov = r.company_overview
    opps = r.ai_opportunities
    win = next((o for o in opps if o.is_recommended), opps[0] if opps else None)
    slides = [
        {"title": p.title if p else f"AI opportunities for {r.business_name}",
         "subtitle": f"Prepared for {p.addressed_to if p else 'the leadership team'}, {r.business_name} · {_date(d)}",
         "bullets": [], "notes": "Introduce the brief: one recommended AI pilot, the evidence behind it, and a next step."},
        {"title": "Company snapshot", "bullets": [x for x in [
            _clip(ov.what_they_do, 170), f"Industry: {ov.industry}" + (f" · {ov.sub_industry}" if ov.sub_industry else ""),
            f"Headquarters: {ov.headquarters}" if ov.headquarters else None,
            f"Revenue: {ov.scale.revenue}" if ov.scale.revenue else None,
            f"Portfolio: {ov.scale.projects_or_portfolio}" if ov.scale.projects_or_portfolio else None,
            "Leadership: " + ("; ".join(ov.leadership) if ov.leadership else "not confirmed by recent sources"),
        ] if x], "notes": "Every figure here is from a dated, cited source; see the Sources slide."},
    ]
    heard = []
    if p and p.opening:
        heard.append(_clip(p.opening.text, 220) + _ref(d.marks("pitch-opening")))
    heard += [_clip(t, 160) + _ref(n) for t, n in d.lines("why_we_reached_out")]
    slides.append({"title": "What we heard", "bullets": heard[:MAX_BULLETS] or ["No recent CEO statements were found."],
                   "notes": ("Open on the CEO's own words." if p and p.ceo_statements_found else
                             "No verifiable CEO statement was found, so this opens on the newest cited fact.")})
    slides.append({"title": "Top challenges", "bullets": [
        f"{c.title}{_ref(d.marks(c.id))}: {_clip(c.reasoning, 120)}" for c in r.business_challenges[:MAX_BULLETS]],
        "notes": "Each challenge is argued from research signals; the full reasoning is in the report."})
    slides.append({"title": "Ranked AI opportunities", "bullets": [], "table": (
        ["#", "Opportunity", "Score", "Evidence", "Effort"],
        [[str(o.rank or "–"), _clip(o.title, 60), f"{o.weighted_score:.0f}" if o.weighted_score is not None else "–",
          f"{o.evidence_share:.0%}" if o.evidence_share is not None else "–", _clip(o.effort.split("·")[0], 20)]
         for o in opps[:MAX_BULLETS]]),
        "notes": "Scores are computed in Python from the rubric; ROI is discounted when its inputs are assumptions."
                 + (" The winner holds under conservative assumptions." if r.sensitivity and r.sensitivity.winner_stable
                    else " The winner changes under conservative assumptions; say so." if r.sensitivity else "")})
    if win:
        bvb = win.build_vs_buy
        slides.append({"title": f"Recommended: {_clip(win.title, 70)}", "bullets": [x for x in [
            f"Problem: {_clip(win.problem_solved, 140)}", f"How it works: {_clip(win.ai_mechanism, 160)}",
            f"Applies to: {_clip(win.applies_to, 120)}", f"Expected impact: {_clip(win.expected_impact, 120)}",
            f"Build vs buy: {bvb.decision}" + (f" ({', '.join(bvb.vendors)})" if bvb and bvb.vendors else "") if bvb else None,
        ] if x], "notes": _clip(win.why_not or "", 300) or "Why this one: it scored highest on the weighted rubric."})
        pilot = sorted(win.pilot_30_60_90, key=lambda m: m.day)
        slides.append({"title": "30/60/90-day pilot", "bullets": [
            f"Day {m.day}: {_clip(m.milestone, 90)} ({m.kpi}: {m.target})" for m in pilot]
            + [f"Data: {x.source} ({x.status})" for x in win.data_readiness][: MAX_BULLETS - len(pilot)]
            or ["Pilot plan not available for this run."],
            "notes": "Targets are measurable so the pilot can be judged at day 90."})
    roi = d.roi
    slides.append({"title": "ROI: conservative vs optimistic", "bullets": [], "table": (
        ["", "Conservative", "Optimistic"],
        [["Annual value", usd(roi.annual_value_usd_low), usd(roi.annual_value_usd_high)],
         ["Net annual value", usd(roi.net_annual_value_usd_low), usd(roi.net_annual_value_usd_high)],
         ["Payback (months)", _num(roi.payback_months_worst), _num(roi.payback_months_best)],
         ["3-year ROI", _pct(roi.three_year_roi_pct_low), _pct(roi.three_year_roi_pct_high)]]) if roi else None,
        **({} if roi else {"bullets": ["The ROI model hasn't been built for this run."]}),
        "notes": "Computed in Python from the line items in the pitch; assumptions are listed in the report."})
    risks = [f"Biggest risk: {_clip(win.biggest_risk, 160)}"] if win and win.biggest_risk else []
    if r.sensitivity and not r.sensitivity.winner_stable:
        risks.append("The ranking changes under conservative assumptions; validate the value drivers in the pilot.")
    comp = [f"{c.title}: {_clip(c.note, 110)}" for c in (win.compliance if win else [])][: MAX_BULLETS - len(risks)]
    slides.append({"title": "Risks and compliance", "bullets": (risks + comp) or ["No specific risks recorded."],
                   "notes": "Compliance notes come from a curated list (data/compliance.yaml), not from memory."})
    slides.append({"title": "Next step and sources", "bullets": [_clip(p.closing, 200) if p else "Book a 30-minute walkthrough."]
                   + [f"[{c.n}] {_clip(c.title or c.url, 70)}" + (f", {c.date}" if c.date else "") for c in r.citations[:4]]
                   + ([f"…and {len(r.citations) - 4} more in the full report."] if len(r.citations) > 4 else []),
                   "notes": "All sources with dates and links: " + "; ".join(f"[{c.n}] {c.url}" for c in r.citations)})
    for s in slides:
        s["bullets"] = s["bullets"][:MAX_BULLETS]
    return slides


def _ref(nums: list[int]) -> str:
    return " " + "".join(f"[{n}]" for n in nums) if nums else ""


def _num(x):
    return "not reached" if x is None else f"{x:.0f}"


def _pct(x):
    return "n/a" if x is None else f"{x:,.0f}%"


def deck_pptx(d: ExportData) -> bytes:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    accent = _rgb(d.accent)
    blank = prs.slide_layouts[6]
    for i, s in enumerate(deck_outline(d)):
        slide = prs.slides.add_slide(blank)
        bar = slide.shapes.add_shape(1, 0, 0, Inches(0.18), prs.slide_height)
        bar.fill.solid()
        bar.fill.fore_color.rgb = accent
        bar.line.fill.background()
        top = Inches(2.6) if i == 0 else Inches(0.55)
        tb = slide.shapes.add_textbox(Inches(0.7), top, Inches(11.9), Inches(1.2))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.text = s["title"]
        tf.paragraphs[0].runs[0].font.size = Pt(36 if i == 0 else 28)
        tf.paragraphs[0].runs[0].font.bold = True
        if s.get("subtitle"):
            para = tf.add_paragraph()
            para.text = s["subtitle"]
            para.runs[0].font.size = Pt(16)
            para.runs[0].font.color.rgb = RGBColor(0x5B, 0x62, 0x70)
        if s["bullets"]:
            body = slide.shapes.add_textbox(Inches(0.7), Inches(1.7), Inches(11.9), Inches(5.3)).text_frame
            body.word_wrap = True
            for j, b in enumerate(s["bullets"]):
                para = body.paragraphs[0] if j == 0 else body.add_paragraph()
                para.text = "• " + b
                para.runs[0].font.size = Pt(18)
                para.space_after = Pt(10)
        if s.get("table"):
            head, rows = s["table"]
            y = Inches(1.9) if not s["bullets"] else Inches(5.0)
            shape = slide.shapes.add_table(len(rows) + 1, len(head), Inches(0.7), y, Inches(11.9),
                                           Emu(Inches(0.5) * (len(rows) + 1)))
            for c, h in enumerate(head):
                shape.table.cell(0, c).text = h
            for rr, row in enumerate(rows, 1):
                for c, val in enumerate(row):
                    shape.table.cell(rr, c).text = val
        slide.notes_slide.notes_text_frame.text = s["notes"]
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------------------------------- email
def email_draft(d: ExportData) -> dict:
    p = d.report.ceo_pitch
    if p is None:
        raise ValueError("This run has no CEO pitch yet.")
    body = p.email_body.strip()
    if "attach" not in body.lower():
        body = body.replace("[Your Name]", "").rstrip() + "\n\nI've attached a one-page summary.\n\n[Your Name]"
    return {"subject": p.email_subject.strip(), "body": body, "words": len(body.split())}


def gmail_url(subject: str, body: str, to: str = "") -> str:
    return "https://mail.google.com/mail/?" + urlencode({"view": "cm", "fs": "1", "to": to, "su": subject, "body": body},
                                                         quote_via=quote)


def mailto_url(subject: str, body: str, to: str = "", limit: int = MAILTO_LIMIT) -> tuple[str, bool]:
    """mailto: link kept under `limit` characters; the body is cut at a sentence if needed. Returns (url, cut)."""
    def build(b: str) -> str:
        return f"mailto:{quote(to, safe='@,')}?subject={quote(subject)}&body={quote(b)}"

    url = build(body)
    if len(url) <= limit:
        return url, False
    sentences = re.split(r"(?<=[.!?])\s+", body)
    while sentences:
        sentences.pop()
        url = build(" ".join(sentences) + "\n\n(The full note is in the attached one-page PDF.)")
        if len(url) <= limit:
            return url, True
    return build("")[:limit], True


def eml_bytes(d: ExportData, pitch: bytes, to: str = "") -> bytes:
    draft = email_draft(d)
    msg = EmailMessage(policy=SMTP)
    if to:
        msg["To"] = to
    msg["Subject"] = draft["subject"]
    msg["X-Unsent"] = "1"           # opens as an unsent draft in Apple Mail and Outlook; nothing is sent
    msg.set_content(draft["body"])
    msg.add_attachment(pitch, maintype="application", subtype="pdf", filename=f"{d.slug}-pitch.pdf")
    return msg.as_bytes()


# ------------------------------------------------------------------------------------------- all
def build_all(d: ExportData) -> dict[str, bytes]:
    pitch, _info = pitch_pdf(d)
    report, _engine = report_pdf(d)
    return {FILES["pptx"]: deck_pptx(d), FILES["report.pdf"]: report, FILES["pitch.pdf"]: pitch,
            FILES["eml"]: eml_bytes(d, pitch)}


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def write_exports(out_dir: Path) -> list[Path]:
    from utils.export.data import load

    files = build_all(load(out_dir))
    paths = []
    for name, data in files.items():
        path = out_dir / name
        path.write_bytes(data)
        paths.append(path)
    return paths
