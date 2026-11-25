"""Phase 8 (exports) tests, against demo fixtures: deck, PDFs, email, .eml, zip, API and CLI. No LLM calls."""
from __future__ import annotations

import email
import io
import sys
import zipfile
from email import policy
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from pptx import Presentation  # noqa: E402

from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import BUSINESS, FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.export.data import INK_BLUE, load  # noqa: E402
from utils.export.documents import (  # noqa: E402
    FILES, MAILTO_LIMIT, MAX_BULLETS, build_all, deck_outline, deck_pptx, email_draft, eml_bytes, gmail_url,
    mailto_url, pitch_html, pitch_pdf, report_html, zip_bytes,
)
from utils.export.pdf import PDFUnavailable, html_to_pdf, page_count  # noqa: E402


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("exports")
    mp = pytest.MonkeyPatch()
    mp.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    mp.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")
    run_pipeline(BUSINESS, settings=settings(tmp), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    mp.undo()
    return tmp / "maple-street-dental"


@pytest.fixture(scope="module")
def pdf_ok():
    try:
        html_to_pdf("<p>probe</p>")
        return True
    except PDFUnavailable:
        return False


def needs_pdf(pdf_ok):
    if not pdf_ok:
        pytest.skip("no PDF engine (Playwright, WeasyPrint or Chrome) on this machine")


# ------------------------------------------------------------------------------------------- deck
def test_deck_has_ten_slides_with_notes_and_bullet_limits(run_dir):
    d = load(run_dir)
    outline = deck_outline(d)
    assert len(outline) == 10
    assert [s["title"] for s in outline][1:4] == ["Company snapshot", "What we heard", "Top challenges"]
    assert outline[-1]["title"] == "Next step and sources"
    prs = Presentation(io.BytesIO(deck_pptx(d)))
    assert len(prs.slides) == 10
    assert prs.slide_width / prs.slide_height == pytest.approx(16 / 9, abs=0.01)
    for slide, spec in zip(prs.slides, outline):
        assert slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip()
        bullets = [p for sh in slide.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs
                   if p.text.startswith("• ")]
        assert len(bullets) == len(spec["bullets"]) <= MAX_BULLETS
    # citations appear on the last slide's notes with their URLs
    assert all(c.url in outline[-1]["notes"] for c in d.report.citations)


def test_deck_uses_brand_accent_or_ink_blue(run_dir):
    d = load(run_dir)
    assert d.accent.startswith("#") and len(d.accent) == 7
    d.profile.brand.primary_color_hex = "not-a-colour"
    from utils.export.data import _hex
    assert _hex(d.profile.brand.primary_color_hex) == INK_BLUE


# ------------------------------------------------------------------------------------------- PDFs
def test_pitch_html_has_citations_and_never_goes_below_10pt(run_dir):
    d = load(run_dir)
    html = pitch_html(d)
    assert 'class="cite">[1]' in html and "[no source]" in html and "font-size: 10.5pt" in html
    short = pitch_html(d, short=True, font_pt=10)
    assert d.report.ceo_pitch.short_version in short and "font-size: 10pt" in short


def test_pitch_pdf_is_exactly_one_page(run_dir, pdf_ok):
    needs_pdf(pdf_ok)
    pdf, info = pitch_pdf(load(run_dir))
    assert page_count(pdf) == 1 and info["font_pt"] >= 10


def test_long_pitch_falls_back_to_short_version(run_dir, pdf_ok):
    needs_pdf(pdf_ok)
    d = load(run_dir)
    d.report.ceo_pitch.why_we_reached_out = "A long paragraph that keeps going. " * 140
    d.report.trace = None                                   # render the paragraph itself, not trace lines
    pdf, info = pitch_pdf(d)
    assert page_count(pdf) == 1 and info["short"] is True


def test_report_pdf_has_cover_toc_and_dated_sources(run_dir, pdf_ok):
    d = load(run_dir)
    html = report_html(d)
    assert "pitch claims verified" in html and "Contents" in html and 'href="#s5"' in html
    assert all(c.url in html for c in d.report.citations) and d.report.citations[0].date in html
    needs_pdf(pdf_ok)
    from utils.export.documents import report_pdf
    pdf, _ = report_pdf(d)
    assert page_count(pdf) >= 5


# ------------------------------------------------------------------------------------------- email
def test_email_draft_links_and_mailto_limit(run_dir):
    d = load(run_dir)
    draft = email_draft(d)
    assert draft["words"] <= 200 and "attached" in draft["body"].lower()
    q = parse_qs(urlparse(gmail_url(draft["subject"], draft["body"])).query)
    assert q["view"] == ["cm"] and q["su"] == [draft["subject"]] and "to" not in q or q.get("to") == [""]
    url, cut = mailto_url(draft["subject"], draft["body"])
    assert url.startswith("mailto:?subject=") and len(url) <= MAILTO_LIMIT and not cut
    long_url, cut = mailto_url(draft["subject"], "This sentence is long enough. " * 200, to="a@b.co")
    assert cut and len(long_url) <= MAILTO_LIMIT and long_url.startswith("mailto:a@b.co?")


def test_eml_parses_with_pdf_attachment_and_no_recipient_by_default(run_dir):
    d = load(run_dir)
    raw = eml_bytes(d, b"%PDF-1.4 fake")
    msg = email.message_from_bytes(raw, policy=policy.default)
    assert msg["To"] is None and msg["X-Unsent"] == "1" and msg["Subject"] == email_draft(d)["subject"]
    parts = list(msg.iter_attachments())
    assert len(parts) == 1 and parts[0].get_content_type() == "application/pdf"
    assert parts[0].get_filename() == "maple-street-dental-pitch.pdf"
    with_to = email.message_from_bytes(eml_bytes(d, b"%PDF", to="ceo@example.com"), policy=policy.default)
    assert with_to["To"] == "ceo@example.com"


# ------------------------------------------------------------------------------------------- zip, API, CLI
def test_zip_contains_every_export(run_dir, pdf_ok):
    needs_pdf(pdf_ok)
    files = build_all(load(run_dir))
    z = zipfile.ZipFile(io.BytesIO(zip_bytes(files)))
    assert sorted(z.namelist()) == sorted(FILES.values())
    assert page_count(z.read(FILES["pitch.pdf"])) == 1


def test_api_endpoints(run_dir, monkeypatch):
    from fastapi.testclient import TestClient

    import api.index as api
    monkeypatch.setenv("OUTPUTS_DIR", str(run_dir.parent))
    c = TestClient(api.app)
    r = c.get("/api/examples/maple-street-dental/export/email")
    assert r.status_code == 200 and r.json()["to"] == "" and r.json()["mailto_url"].startswith("mailto:")
    r = c.get("/api/examples/maple-street-dental/export/pptx")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert c.get("/api/examples/maple-street-dental/export/docx").status_code == 404
    assert c.get("/api/examples/no-such-run/export/pptx").status_code == 404


def test_royal_technosoft_pitch_export(pdf_ok):
    needs_pdf(pdf_ok)
    from fastapi.testclient import TestClient

    import api.index as api
    royal_dir = ROOT / "outputs" / "royal-technosoft"
    if not royal_dir.exists():
        pytest.skip("outputs/royal-technosoft not present")
    d = load(royal_dir)
    pdf, info = pitch_pdf(d)
    assert page_count(pdf) == 1 and info["font_pt"] >= 10

    c = TestClient(api.app)
    r_pdf = c.get("/api/examples/royal-technosoft/export/pitch.pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert "attachment" in r_pdf.headers["content-disposition"]

    r_html = c.get("/api/examples/royal-technosoft/export/pitch.html")
    assert r_html.status_code == 200
    assert "text/html" in r_html.headers["content-type"]


def test_cli_export_flag_writes_06_files(tmp_path, monkeypatch, pdf_ok):
    needs_pdf(pdf_ok)
    import run_pipeline as rp
    real_run = rp.run_pipeline

    def fake_run(*a, **kw):
        return real_run(BUSINESS, settings=settings(tmp_path), llm=FakeLLM(), research=FakeResearch(),
                               ui=quiet_ui(), build_prototype=False)

    monkeypatch.setattr(rp, "run_pipeline", fake_run)
    monkeypatch.setattr(rp, "PipelineUI", quiet_ui)
    assert rp.main([BUSINESS, "--export"]) == 0
    out = tmp_path / "maple-street-dental"
    assert all((out / name).exists() for name in FILES.values())
