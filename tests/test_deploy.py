"""Deployment pieces: one-URL static serving, optional report persistence, workflow and Dockerfile shape."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
import yaml  # noqa: E402

from utils import persist  # noqa: E402


@pytest.fixture
def served(tmp_path, monkeypatch):
    """The API app with a fake built frontend mounted at /."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>AI Opportunity Studio</title>")
    (dist / "assets" / "app.js").write_text("console.log('ok')")
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path / "outputs"))
    import api.index as api
    api = importlib.reload(api)
    from fastapi.testclient import TestClient
    yield TestClient(api.app)
    monkeypatch.delenv("FRONTEND_DIST")
    importlib.reload(api)


def test_one_url_serves_ui_assets_and_api(served):
    assert "AI Opportunity Studio" in served.get("/").text
    assert served.get("/assets/app.js").status_code == 200
    assert served.get("/api/health").json()["status"] in ("ok", "config_error")   # API wins over the static mount
    assert served.get("/api/examples").json() == []
    assert served.get("/api/examples/no-such-run").status_code == 404


def test_static_mount_cannot_escape_the_dist_folder(served):
    for path in ("/../../etc/passwd", "/..%2f..%2fetc/passwd", "/%2e%2e/%2e%2e/etc/passwd"):
        r = served.get(path)
        assert r.status_code in (400, 404) or "root:" not in r.text


def test_persistence_is_a_noop_without_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("REPORTS_DATASET", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    (tmp_path / "run").mkdir()
    assert persist.enabled() is False
    assert persist.restore(tmp_path) == 0 and persist.save_run(tmp_path / "run") is False


def test_save_run_uploads_the_folder_without_the_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DATASET", "team/reports")
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    calls = {}

    class FakeApi:
        def upload_folder(self, **kw):
            calls.update(kw)

    monkeypatch.setattr(persist, "_api", lambda: FakeApi())
    run = tmp_path / "sobha"
    run.mkdir()
    assert persist.save_run(run) is True
    assert calls["repo_id"] == "team/reports" and calls["repo_type"] == "dataset" and calls["path_in_repo"] == "sobha"
    assert "cache/**" in calls["ignore_patterns"]


def test_upload_failure_never_breaks_a_run(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DATASET", "team/reports")
    monkeypatch.setenv("HF_TOKEN", "hf_test")

    class Boom:
        def upload_folder(self, **kw):
            raise RuntimeError("network down")

    monkeypatch.setattr(persist, "_api", lambda: Boom())
    (tmp_path / "run").mkdir()
    assert persist.save_run(tmp_path / "run") is False


def test_workflow_and_image_follow_the_space_rules():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "deploy-space.yml").read_text())
    assert wf["jobs"]["deploy"]["needs"] == "test"                       # never deploy a failing main
    text = (ROOT / ".github" / "workflows" / "deploy-space.yml").read_text()
    assert "--exclude docs" in text and "app_port: 7860" in text and "sdk: docker" in text
    assert "secrets.HF_TOKEN" in text and "hf_" not in text              # the token is a secret, never inline
    docker = (ROOT / "Dockerfile").read_text()
    assert "EXPOSE 7860" in docker and "useradd -m -u 1000" in docker and "playwright install" in docker
    assert ".env" in (ROOT / ".dockerignore").read_text().splitlines()
