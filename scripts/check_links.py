"""Check every official URL in the curated lists (data/vendors.yaml, data/compliance.yaml).

    python scripts/check_links.py

Exit code 1 if a link is broken (4xx other than bot-blocking codes, 5xx, or no connection). Sites that
refuse scripted clients (401/403/429, some 400s) are reported as "blocked" for a manual check in a browser.
"""
from __future__ import annotations

import concurrent.futures as cf
import sys
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/126 Safari/537.36"}
BLOCKED = {401, 403, 429}
# Hosts that answer scripted clients with an error page but load normally in a browser (checked by hand,
# 2026-11-25: the FTC CAN-SPAM guide returns 404 to scripts and 200 in a browser).
SCRIPT_HOSTILE_HOSTS = {"www.ftc.gov"}


def links() -> list[tuple[str, str]]:
    out = []
    for items in yaml.safe_load((ROOT / "data" / "vendors.yaml").read_text()).values():
        out += [(v["name"], v["url"]) for v in items]
    for rules in yaml.safe_load((ROOT / "data" / "compliance.yaml").read_text()).values():
        out += [(r["id"], r["url"]) for r in rules]
    return out


def check(item: tuple[str, str]) -> tuple[str, str, str]:
    name, url = item
    try:
        code = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=15).status_code
    except httpx.HTTPError as exc:
        return name, url, f"error ({exc.__class__.__name__})"
    if code < 400:
        return name, url, "ok"
    host = httpx.URL(url).host
    return name, url, "blocked" if code in BLOCKED or host in SCRIPT_HOSTILE_HOSTS else f"broken ({code})"


def main() -> int:
    with cf.ThreadPoolExecutor(8) as pool:
        results = list(pool.map(check, links()))
    for name, url, status in results:
        print(f"{status:12} {name:32} {url}")
    bad = [r for r in results if r[2].startswith(("broken", "error"))]
    print(f"\n{len(results)} links: {sum(r[2] == 'ok' for r in results)} ok, "
          f"{sum(r[2] == 'blocked' for r in results)} blocked for scripts (check in a browser), {len(bad)} broken")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
