"""scripts/build_static.py: the Vercel snapshot is exactly what the API serves, minus legacy and unfinished runs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from run_pipeline import run_pipeline  # noqa: E402
from scripts.build_static import EXPORTS, build  # noqa: E402
from tests.test_pipeline import BUSINESS, FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.export.pdf import PDFUnavailable, html_to_pdf  # noqa: E402


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


def _need_pdf():
    try:
        html_to_pdf("<p>probe</p>")
    except PDFUnavailable:
        pytest.skip("no PDF engine on this machine")


def test_snapshot_has_report_exports_and_list(tmp_path):
    _need_pdf()
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    out = tmp_path / "static"
    assert build(tmp_path, out) == ["maple-street-dental"]
    listing = json.loads((out / "examples.json").read_text())
    assert [r["slug"] for r in listing] == ["maple-street-dental"] and listing[0]["legacy"] is False
    report = json.loads((out / "runs" / "maple-street-dental.json").read_text())
    assert report["report"]["ceo_pitch"] and report["prototype_url"] is None and report["report"]["key_metrics"]
    folder = out / "exports" / "maple-street-dental"
    assert sorted(p.name for p in folder.iterdir()) == sorted([*EXPORTS.values(), "email.json"])
    assert (folder / "pitch.pdf").read_bytes().startswith(b"%PDF")
    email = json.loads((folder / "email.json").read_text())
    assert set(email) == {"subject", "body", "words"}                 # links are built in the browser, not baked in


def test_legacy_and_unfinished_runs_are_left_out_unless_asked(tmp_path):
    _need_pdf()
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    run = tmp_path / "maple-street-dental"
    meta = json.loads((run / "00_run_meta.json").read_text())
    meta["stages"] = {}                                              # as if saved before the fact checks
    (run / "00_run_meta.json").write_text(json.dumps(meta))
    (run / "04_verification.json").unlink()
    assert build(tmp_path, tmp_path / "a") == []
    assert build(tmp_path, tmp_path / "b", include_legacy=True) == ["maple-street-dental"]
    assert build(tmp_path, tmp_path / "c", include_legacy=True, only={"someone-else"}) == []


def test_vercel_files_follow_the_rules():
    cfg = json.loads((ROOT / "frontend" / "vercel.json").read_text())
    assert cfg["buildCommand"] == "npm run build:static" and cfg["outputDirectory"] == "dist"
    mw = (ROOT / "frontend" / "middleware.ts").read_text()
    assert "SITE_PASSWORD" in mw and "401" in mw and "503" in mw       # asks for a password; locked if none is set
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    assert pkg["scripts"]["build:static"] == "VITE_STATIC=1 npm run build"
    # the snapshot (binary PDFs) must never go into the Hugging Face Space repo or image
    assert "frontend/public/data" in (ROOT / ".github" / "workflows" / "deploy-space.yml").read_text()
    assert "frontend/public/data" in (ROOT / ".dockerignore").read_text()
