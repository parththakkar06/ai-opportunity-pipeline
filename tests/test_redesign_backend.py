"""Phase 9 backend pieces: cited key metrics, figure compaction, brand accent rule, run_meta, pitch preview."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from agents.report import build_report  # noqa: E402
from agents.trace import _compact_metric  # noqa: E402
from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import BUSINESS, FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.export.data import INK_BLUE, _hex, contrast  # noqa: E402


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("redesign")
    mp = pytest.MonkeyPatch()
    mp.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    mp.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")
    run_pipeline(BUSINESS, settings=settings(tmp), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    mp.undo()
    return tmp / "maple-street-dental"


def test_key_metrics_are_cited_dated_and_short(run_dir):
    r = build_report(run_dir)
    assert 3 <= len(r.key_metrics) <= 5
    numbers = {c.n for c in r.citations}
    for m in r.key_metrics:
        assert m.citations and set(m.citations) <= numbers and m.date and m.facts
        assert len(m.value) <= 22
    labels = [m.label for m in r.key_metrics]
    assert "Revenue, FY25" in labels and "Founder & CEO" in labels


@pytest.mark.parametrize("value,expected", [
    ("FY25 revenue ~$9M (estimated)", ("Revenue, FY25", "~$9M")),
    ("Q1 FY27 sales bookings ₹2,700 crore", ("Revenue, Q1 FY27", "₹2,700 crore")),
    ("FY26 revenue of Rs 4,812 crore, up 16% year on year", ("Revenue, FY26", "Rs 4,812 crore")),
    ("2 clinics, 14 chairs", ("Revenue", "2 clinics, 14 chairs")),          # short values kept as written
    ("Leading developer in the south of India", ("Revenue", "")),          # prose isn't a figure: left out
])
def test_compact_metric(value, expected):
    assert _compact_metric("Revenue", value) == expected


@pytest.mark.parametrize("brand", ["#FFD200", "#E31837", "#0F4C81", "#38BDF8"])
def test_brand_accent_always_reads_at_4_5_to_1(brand):
    accent = _hex(brand)
    assert min(contrast(accent, "#FBFAF7"), contrast(accent, "#FFFFFF")) >= 4.5


def test_grey_or_missing_brand_falls_back_to_ink_blue():
    assert _hex("#777777") == INK_BLUE and _hex(None) == INK_BLUE and _hex("teal") == INK_BLUE


def test_payload_carries_run_meta_and_brand(run_dir, monkeypatch):
    from fastapi.testclient import TestClient

    import api.index as api
    monkeypatch.setenv("OUTPUTS_DIR", str(run_dir.parent))
    body = TestClient(api.app).get("/api/examples/maple-street-dental").json()
    meta = body["run_meta"]
    assert meta["stages"]["1"]["calls"] >= 2 and meta["total_input_tokens"] > 0
    assert "key_metrics" in body["report"] and "brand_color" in body["report"]


def test_pitch_preview_is_the_export_html_and_cached_on_disk(run_dir, monkeypatch):
    from fastapi.testclient import TestClient

    import api.index as api
    monkeypatch.setenv("OUTPUTS_DIR", str(run_dir.parent))
    client = TestClient(api.app)
    first = client.get("/api/examples/maple-street-dental/export/pitch.html")
    assert first.status_code == 200 and first.headers["content-type"].startswith("text/html")
    assert "default-src 'none'" in first.headers["content-security-policy"]
    assert "Why we reached out" in first.text and (run_dir / "06_pitch_preview.html").exists()
    assert client.get("/api/examples/maple-street-dental/export/pitch.html").text == first.text
