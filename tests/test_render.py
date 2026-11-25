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
