"""Bake saved runs into plain files for a static site (Vercel): frontend/public/data/.

    python scripts/build_static.py                 # current runs in outputs/ -> frontend/public/data
    python scripts/build_static.py --include-legacy --only sobha,adani-realty

It calls the app's own API in-process (no server, no model or search calls) and saves every response, so each
file is exactly what the live app would serve:

    data/examples.json                 the saved-reports list
    data/runs/<slug>.json              one report (what GET /api/examples/<slug> returns)
    data/exports/<slug>/               pitch.pdf  report.pdf  deck.pptx  exports.zip  outreach.eml
                                       pitch.html (the exact A4 page)  email.json (the draft)

Run it on a machine with Chrome (the PDFs are built with it), commit frontend/public/data, and Vercel serves it.
Runs saved before the fact checks ("legacy") and runs without a finished pitch are left out unless you ask.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXPORTS = {  # live API kind -> static file name
    "pitch.pdf": "pitch.pdf", "report.pdf": "report.pdf", "pptx": "deck.pptx", "zip": "exports.zip",
    "eml": "outreach.eml", "pitch.html": "pitch.html",
}


def build(outputs: Path, out: Path, include_legacy: bool = False, only: set[str] | None = None) -> list[str]:
    previous = os.environ.get("OUTPUTS_DIR")
    os.environ["OUTPUTS_DIR"] = str(outputs)
    try:
        return _build(out, include_legacy, only)
    finally:                                   # don't leak the setting into whatever runs next (tests, a shell)
        if previous is None:
            os.environ.pop("OUTPUTS_DIR", None)
        else:
            os.environ["OUTPUTS_DIR"] = previous


def _build(out: Path, include_legacy: bool, only: set[str] | None) -> list[str]:
    from fastapi.testclient import TestClient

    import api.index as api

    client = TestClient(api.app)
    listing = client.get("/api/examples").json()
    chosen, skipped = [], []
    for run in listing:
        slug = run["slug"]
        if only and slug not in only:
            continue
        if run.get("legacy") and not include_legacy:
            skipped.append(f"{slug}: saved before the fact checks (use --include-legacy)")
        elif not run.get("complete") and 4 not in run.get("stages_completed", []):
            skipped.append(f"{slug}: no finished pitch yet")
        else:
            chosen.append(run)

    if out.exists():
        shutil.rmtree(out)
    (out / "runs").mkdir(parents=True)
    for run in chosen:
        slug = run["slug"]
        payload = client.get(f"/api/examples/{slug}")
        payload.raise_for_status()
        body = payload.json()
        body["prototype_url"] = None              # prototypes aren't part of the snapshot
        (out / "runs" / f"{slug}.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        folder = out / "exports" / slug
        folder.mkdir(parents=True)
        for kind, name in EXPORTS.items():
            res = client.get(f"/api/examples/{slug}/export/{kind}")
            if res.status_code != 200:
                raise SystemExit(f"{slug}: export '{kind}' failed ({res.status_code}): {res.text[:200]}")
            (folder / name).write_bytes(res.content)
        email = client.get(f"/api/examples/{slug}/export/email").json()
        for key in ("gmail_url", "mailto_url", "mailto_shortened", "to"):
            email.pop(key, None)                  # links are built in the browser, where the recipient is typed
        (folder / "email.json").write_text(json.dumps(email, ensure_ascii=False), encoding="utf-8")
        print(f"  {slug}: report + {len(EXPORTS) + 1} files")
    for run in chosen:
        run["prototype_available"] = False
    (out / "examples.json").write_text(json.dumps(chosen, ensure_ascii=False), encoding="utf-8")
    for line in skipped:
        print("  skipped", line)
    return [r["slug"] for r in chosen]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--outputs", type=Path, default=ROOT / "outputs")
    p.add_argument("--out", type=Path, default=ROOT / "frontend" / "public" / "data")
    p.add_argument("--include-legacy", action="store_true")
    p.add_argument("--only", help="Comma-separated run folders to include")
    args = p.parse_args(argv)
    print(f"Building the static snapshot from {args.outputs} ...")
    slugs = build(args.outputs, args.out, args.include_legacy, set(args.only.split(",")) if args.only else None)
    if not slugs:
        print("Nothing to publish: no current, finished runs found.")
        return 1
    size = sum(f.stat().st_size for f in args.out.rglob("*") if f.is_file()) / 1e6
    print(f"Done: {len(slugs)} report(s), {size:.1f} MB in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
