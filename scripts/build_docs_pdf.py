"""Build one readable documentation PDF from the project's Markdown docs.

    python scripts/build_docs_pdf.py
    python scripts/build_docs_pdf.py --app-url https://your-app.onrender.com --site-url https://your-site.vercel.app \
        --video-url https://...

Output: docs/AI_Opportunity_Pipeline_Documentation.pdf

It stitches together a short overview, a product tour (screenshots from docs/screenshots), docs/APPROACH.md,
docs/AI_USAGE.md, and the results and limits (the table in docs/eval_results.md, so rebuilding after a new eval run
updates it). Mermaid diagrams are rendered to real diagrams (this needs internet once, to load mermaid from a CDN, and
Chrome or Chromium via Playwright). Relative links in the Markdown become links to the GitHub repo.
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
TOUR = [
    ("03-report.png", "The report: a header with data quality and verification badges, key figures that each carry a dated citation, and a contents list that follows you down the page."),
    ("04-opportunities.png", "Ranked AI opportunities. Each row expands into the problem, how the AI works, build versus buy with real vendors, a 30/60/90-day pilot, data readiness and compliance."),
    ("05-ceo-pitch.png", "The one-page CEO pitch, shown exactly as the exported PDF prints it. Every claim carries a numbered source; a line with no source says so."),
    ("06-how-it-works.png", "The pipeline map: four model stages, with Python doing the parts that must be exact."),
]


def repo_url() -> str:
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return re.sub(r"\.git$", "", url)


def md_engine(blob_base: str) -> MarkdownIt:
    md = MarkdownIt("commonmark").enable("table")
    default_fence = md.renderer.rules["fence"]

    def fence(tokens, idx, options, env):
        token = tokens[idx]
        if token.info.strip() == "mermaid":
            return f'<div class="diagram"><pre class="mermaid">{html.escape(token.content)}</pre></div>\n'
        return default_fence(tokens, idx, options, env)

    md.renderer.rules["fence"] = fence

    default_link = md.renderer.rules.get("link_open") or (lambda t, i, o, e: md.renderer.renderToken(t, i, o, e))

    def link_open(tokens, idx, options, env):
        href = tokens[idx].attrGet("href") or ""
        if blob_base and href and not re.match(r"^(https?:|mailto:|#)", href):
            tokens[idx].attrSet("href", f"{blob_base}/{href.lstrip('./')}")
        return default_link(tokens, idx, options, env)

    md.renderer.rules["link_open"] = link_open
    return md


def drop_title(text: str) -> str:
    """Remove the document's own H1 (the PDF supplies chapter titles)."""
    return re.sub(r"\A# .*\n+", "", text, count=1)


def data_uri(path: Path, width: int = 1500) -> str:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=84, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def results_markdown() -> str:
    path = DOCS / "eval_results.md"
    if not path.exists():
        return "_No evaluation has been run yet. See `python scripts/eval.py`._"
    text = path.read_text(encoding="utf-8")
    table = "\n".join(line for line in text.splitlines() if line.startswith("|"))
    current = len(re.findall(r"\|\s*current\s*\|", table))
    legacy = len(re.findall(r"\|\s*legacy\s*\|", table))
    if current:
        status = f"The table covers {current} run(s) made with the final pipeline" + (f" and {legacy} earlier (legacy) run(s)." if legacy else ".")
    else:
        status = ("**Status:** the table only has runs saved before the fact checks were added (\"legacy\"), so it has no "
                  "verifier, citation or per-stage token columns yet. Fresh runs of the final pipeline on the example "
                  "companies are the next step.")
    notes = "\n".join(line for line in text.splitlines() if line.startswith("- "))
    return f"{status}\n\n{table}\n\n{notes}"


def more_time_markdown() -> str:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"## With more time\n+(.*)\Z", text, flags=re.S)
    return m.group(1).strip() if m else ""


def overview_markdown(links: list[tuple[str, str]]) -> str:
    link_lines = "\n".join(f"- **{label}:** {url}" for label, url in links)
    return f"""
The task asks for a system that takes a company name and produces a structured intelligence report. This project does that
for any company, and goes further by making every claim checkable.

## What it produces

| The task asks for | Where it is in the app |
|---|---|
| 1. Company overview: what it does, industry, scale, geographic presence | Report section 1 |
| 2. Key business information: offerings, recent developments, expansion plans, public information | Report section 2 |
| 3. Potential challenges (operational, sales, customer experience), with reasoning | Report section 3: each challenge is laid out as evidence, then reasoning, then impact |
| 4. AI opportunities, company-specific | Report section 4: ranked, each with a pilot plan, vendors and compliance notes |
| 5. A one-page personalized pitch to the CEO | Report section 5, and the one-page PDF export |

It also produces a full-report PDF with numbered sources, a ten-slide deck and an email draft (never sent automatically).

## The idea in one paragraph
Language models read and write; Python decides and checks. Models turn web pages into dated facts, diagnose challenges and
propose ideas. Code assigns every fact an ID and a date, decides which source is newest, checks quotes word for word,
computes the ranking and the return on investment, and verifies every name, figure and period in the pitch against the
evidence before anything is saved. That is how the system avoids the failure that motivated it: a pitch addressed to a
former managing director, using out-of-date figures, built on an assumed return.

## Links
{link_lines}

## How to run it
- **No keys needed (demo mode):** `python scripts/demo_api.py`, then start the front end. It runs the real app with fake model
  and search calls.
- **Real runs:** copy `.env.example` to `.env`, add a model key, then `python run_pipeline.py "Company Name"` or use the web
  app. Search works without a key (DuckDuckGo).
- **Hosted:** the full app runs on Render (backend and interface), and the same interface can be hosted on Vercel pointing
  at it. Step-by-step guides are in the repository's `docs/` folder.
"""


CSS = """
@page { size: A4; margin: 16mm 16mm 18mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; color: #1c1f24; font-size: 10.2pt;
       line-height: 1.5; margin: 0; }
h1, h2, h3 { font-family: Georgia, 'Times New Roman', serif; color: #111; line-height: 1.22; }
h1 { font-size: 24pt; margin: 0 0 6mm; padding-top: 2mm; page-break-before: always; border-bottom: 2px solid #1f3a6e;
     padding-bottom: 3mm; }
h2 { font-size: 15pt; margin: 8mm 0 3mm; break-after: avoid; }
h3 { font-size: 12pt; margin: 6mm 0 2mm; break-after: avoid; }
p { margin: 0 0 3mm; } li { margin-bottom: 1.2mm; }
a { color: #1f3a6e; text-decoration: none; word-break: break-word; }
code { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 8.8pt; background: #f1efe9; padding: 0 3px;
       border-radius: 3px; }
pre { background: #f6f5f1; border: 1px solid #e3e0d8; border-radius: 4px; padding: 3mm; font-size: 8.2pt; overflow: hidden;
      white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0 5mm; font-size: 9pt; break-inside: auto; }
th, td { text-align: left; vertical-align: top; padding: 1.6mm 2.2mm; border-bottom: 1px solid #e3e0d8; }
th { background: #f3f1ec; font-weight: 600; } tr { break-inside: avoid; }
blockquote { margin: 3mm 0; padding: 1mm 4mm; border-left: 3px solid #1f3a6e; background: #f6f5f1; }
.diagram { margin: 4mm 0 6mm; text-align: center; break-inside: avoid; }
.diagram svg { max-width: 100%; max-height: 190mm; height: auto; }
figure { margin: 4mm 0; break-inside: avoid; } figure img { display: block; width: 86%; margin: 0 auto; border: 1px solid #e3e0d8;
         border-radius: 3px; }
figcaption { text-align: center; }
figcaption { font-size: 8.8pt; color: #5b6270; margin-top: 1.5mm; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: center; }
.cover .kicker { color: #5b6270; font-size: 11pt; } .cover h1 { font-size: 34pt; border: 0; page-break-before: avoid;
       margin: 3mm 0; padding: 0; }
.cover .rule { width: 18mm; height: 3px; background: #1f3a6e; margin: 4mm 0 6mm; }
.cover .sub { font-size: 13pt; color: #3e4046; max-width: 140mm; }
.cover .meta { margin-top: 14mm; font-size: 9.5pt; color: #5b6270; }
.cover .meta a { color: #1f3a6e; }
.toc { page-break-before: always; } .toc h1 { page-break-before: avoid; }
.toc + h1 { page-break-before: avoid; margin-top: 10mm; }
.toc ol { font-size: 12pt; line-height: 2; padding-left: 7mm; } .toc li span { color: #5b6270; font-size: 9.5pt; }
"""


def build_html(args, md: MarkdownIt) -> str:
    links = []
    repo = repo_url()
    if repo:
        links.append(("Source code", repo))
    for label, value in (("Live app", args.app_url), ("Interface (Vercel)", args.site_url), ("Demo video", args.video_url)):
        if value:
            links.append((label, value))

    chapters: list[tuple[str, str, str]] = []   # (title, one-line description, html)
    chapters.append(("Overview", "What was built and how to run it", md.render(overview_markdown(links))))
    tour = "".join(
        f'<figure><img src="{data_uri(DOCS / "screenshots" / name)}" alt=""><figcaption>{html.escape(cap)}</figcaption></figure>'
        for name, cap in TOUR if (DOCS / "screenshots" / name).exists()
    )
    chapters.append(("Product tour", "Screenshots of the finished app", tour))
    chapters.append(("Approach and architecture", "Design, data flow, decisions and the challenges solved",
                     md.render(drop_title((DOCS / "APPROACH.md").read_text(encoding="utf-8")))))
    chapters.append(("How AI was used", "Tools, model choices, key prompts, and where the AI was wrong",
                     md.render(drop_title((DOCS / "AI_USAGE.md").read_text(encoding="utf-8")))))
    results = md.render(results_markdown())
    more = more_time_markdown()
    if more:
        results += "<h2>With more time</h2>" + md.render(more)
    chapters.append(("Results, limits and next steps", "Evaluation, honest limits and what comes next", results))

    toc = "".join(f"<li>{html.escape(t)} <span>: {html.escape(d)}</span></li>" for t, d, _ in chapters)
    body = "".join(f"<h1>{html.escape(t)}</h1>{h}" for t, _, h in chapters)
    meta = f"Built {date.today().strftime('%-d %B %Y')}" + (f" · {html.escape(args.author)}" if args.author else "")
    link_html = "<br>".join(f'{html.escape(l)}: <a href="{html.escape(u)}">{html.escape(u)}</a>' for l, u in links)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>AI Opportunity Pipeline: documentation</title>
<style>{CSS}</style></head><body>
<section class="cover">
  <div class="kicker">AI/ML Intern Assessment</div><div class="rule"></div>
  <h1>AI Opportunity Pipeline</h1>
  <div class="sub">An AI research and recommendation agent: give it a company name and it produces a cited intelligence
  report, ranked AI opportunities and a one-page pitch to the CEO.</div>
  <div class="meta">{meta}<br><br>{link_html}</div>
</section>
<section class="toc"><h1>Contents</h1><ol>{toc}</ol></section>
{body}
<script src="{MERMAID}"></script>
<script>
  window.__diagrams = 'pending';
  window.addEventListener('load', async () => {{
    try {{
      mermaid.initialize({{ startOnLoad: false, theme: 'neutral', flowchart: {{ htmlLabels: true, useMaxWidth: true }},
                           securityLevel: 'loose' }});
      await mermaid.run({{ querySelector: '.mermaid' }});
      window.__diagrams = 'done';
    }} catch (e) {{ window.__diagrams = 'error: ' + e; }}
  }});
</script></body></html>"""


def render_pdf(page_html: str, out: Path) -> dict:
    from playwright.sync_api import sync_playwright

    footer = ('<div style="font-size:8px;width:100%;text-align:center;color:#666;">AI Opportunity Pipeline · '
              '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')
    with sync_playwright() as p:
        browser = None
        for kwargs in ({"channel": "chrome"}, {}):
            try:
                browser = p.chromium.launch(**kwargs)
                break
            except Exception:  # noqa: BLE001 - try the next browser
                continue
        if browser is None:
            raise SystemExit("No Chrome or Chromium found for Playwright. Install Chrome, or run `playwright install chromium`.")
        try:
            page = browser.new_page(viewport={"width": 1000, "height": 1400})
            page.set_content(page_html, wait_until="load")
            try:
                page.wait_for_function("window.__diagrams !== 'pending'", timeout=60_000)
            except Exception:  # noqa: BLE001
                raise SystemExit("Mermaid didn't load in 60 s. This script needs internet once (it loads mermaid from a CDN).")
            status = page.evaluate("window.__diagrams")
            if status != "done":
                raise SystemExit(f"Diagrams failed to render: {status}")
            total = page.evaluate("document.querySelectorAll('.mermaid').length")
            drawn = page.evaluate("document.querySelectorAll('.mermaid svg').length")
            broken = page.evaluate("[...document.querySelectorAll('.mermaid')].filter(e => /Syntax error|Parse error/i.test(e.textContent)).length")
            pdf = page.pdf(format="A4", print_background=True, display_header_footer=True, header_template="<div></div>",
                           footer_template=footer, prefer_css_page_size=True)
        finally:
            browser.close()
    out.write_bytes(pdf)
    return {"diagrams": total, "drawn": drawn, "broken": broken}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=DOCS / "AI_Opportunity_Pipeline_Documentation.pdf")
    p.add_argument("--app-url", help="The live app (Render)")
    p.add_argument("--site-url", help="The interface on Vercel")
    p.add_argument("--video-url", help="The demo video")
    p.add_argument("--author", help="Your name, shown on the cover")
    args = p.parse_args(argv)
    repo = repo_url()
    md = md_engine(f"{repo}/blob/main" if repo else "")
    stats = render_pdf(build_html(args, md), args.out)
    from pypdf import PdfReader

    pages = len(PdfReader(str(args.out)).pages)
    shown = args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out
    print(f"Wrote {shown}: {pages} pages, {args.out.stat().st_size // 1024} KB; "
          f"diagrams drawn {stats['drawn']}/{stats['diagrams']}, broken {stats['broken']}")
    return 0 if stats["broken"] == 0 and stats["drawn"] == stats["diagrams"] else 1


if __name__ == "__main__":
    sys.exit(main())
