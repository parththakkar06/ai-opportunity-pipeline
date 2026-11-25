"""The Render blueprint and the image it builds."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_render_blueprint_and_image():
    svc = yaml.safe_load((ROOT / "render.yaml").read_text())["services"][0]
    assert svc["runtime"] == "docker" and svc["plan"] == "free" and svc["healthCheckPath"] == "/api/health"
    env = {e["key"]: e for e in svc["envVars"]}
    assert env["OPENROUTER_API_KEY"].get("sync") is False and "value" not in env["OPENROUTER_API_KEY"]   # asked for, never stored
    assert "ACCESS_PASSWORD" not in env                                              # the app is public by design
    docker = (ROOT / "Dockerfile").read_text()
    assert "${PORT:-7860}" in docker and "EXPOSE 7860" in docker                     # Render's $PORT, else Hugging Face's


def test_image_installs_the_driver_library_before_playwright():
    """The first Render build failed with: libatomic.so.1: cannot open shared object file."""
    docker = (ROOT / "Dockerfile").read_text()
    apt = docker.index("apt-get install -y --no-install-recommends libatomic1")
    assert apt < docker.index("&& playwright install --with-deps chromium")   # the commands, not the comment


def test_blueprint_lets_the_vercel_front_end_call_the_api():
    svc = yaml.safe_load((ROOT / "render.yaml").read_text())["services"][0]
    env = {e["key"]: e for e in svc["envVars"]}
    assert env["CORS_ORIGINS"]["value"] == "*"      # public API, no cookies: any site may call it


def test_api_answers_cross_origin_requests_when_cors_is_open(tmp_path, monkeypatch):
    import importlib
    import sys

    from fastapi.testclient import TestClient
    sys.path.insert(0, str(ROOT))
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path))
    import api.index as api
    api = importlib.reload(api)
    c = TestClient(api.app)
    origin = {"Origin": "https://my-team-app.vercel.app"}
    assert c.get("/api/health", headers=origin).headers["access-control-allow-origin"] == "*"
    pre = c.options("/api/analyze/stream", headers={**origin, "Access-Control-Request-Method": "POST",
                                                    "Access-Control-Request-Headers": "content-type"})
    assert pre.status_code == 200 and "POST" in pre.headers["access-control-allow-methods"]
    monkeypatch.delenv("CORS_ORIGINS")
    api = importlib.reload(api)
    assert "access-control-allow-origin" not in TestClient(api.app).get("/api/health", headers=origin).headers   # closed by default
