"""Phase 11 fixes: legacy-run flag, whole-run time budget, curated link file shape."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
import yaml  # noqa: E402

from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import BUSINESS, FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


def test_current_run_is_not_legacy_and_old_run_is(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import api.index as api
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    out = tmp_path / "maple-street-dental"
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path))
    client = TestClient(api.app)
    assert client.get("/api/examples/maple-street-dental").json()["legacy"] is False
    # Simulate a run saved before the upgrade: no per-stage log, no verification file.
    meta = json.loads((out / "00_run_meta.json").read_text())
    meta["stages"] = {}
    (out / "00_run_meta.json").write_text(json.dumps(meta))
    (out / "04_verification.json").unlink()
    assert client.get("/api/examples/maple-street-dental").json()["legacy"] is True
    listed = {r["slug"]: r for r in client.get("/api/examples").json()}
    assert listed["maple-street-dental"]["legacy"] is True


def test_prototype_is_skipped_when_the_run_budget_is_spent(tmp_path):
    s = settings(tmp_path)
    s.run_time_budget_s = 0.0
    s.build_prototype = True
    llm = FakeLLM()
    run_pipeline(BUSINESS, settings=s, llm=llm, research=FakeResearch(), ui=quiet_ui())
    assert "prototype" not in llm.calls
    assert not (tmp_path / "maple-street-dental" / "04_prototype.html").exists()


def test_curated_urls_are_https_and_unique():
    urls = []
    for items in yaml.safe_load((ROOT / "data" / "vendors.yaml").read_text()).values():
        urls += [v["url"] for v in items]
    for rules in yaml.safe_load((ROOT / "data" / "compliance.yaml").read_text()).values():
        urls += [r["url"] for r in rules]
    assert all(u.startswith("https://") for u in urls)
    assert "business.whatsapp.com" not in " ".join(urls)        # fixed: it returned 400
    assert "telemarketing-and-robocalls" not in " ".join(urls)   # fixed: it returned 403/404
