"""Capture the README screenshots from demo mode (no API quota).

Start the demo servers first (see README, "Demo mode"), then:
    python scripts/screenshots.py                  # writes docs/screenshots/*.png
    python scripts/screenshots.py --base http://localhost:5174 --company "Maple Street Dental"
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# Hide the dev-only data toggle and transient toasts, which aren't part of the product.
HIDE = """document.addEventListener('DOMContentLoaded', () => {
  const s = document.createElement('style');
  s.textContent = '[aria-label="Dev data"], [role="status"][aria-live="polite"] > div { display: none !important; }';
  document.head.appendChild(s);
});"""


def settle(page: Page, ms: int = 600) -> None:
    page.wait_for_timeout(ms)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:5174")
    p.add_argument("--company", default="Maple Street Dental")
    args = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    slug = slugify(args.company)

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome")
        except Exception:  # noqa: BLE001 - fall back to Playwright's own Chromium
            browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2,
                                  color_scheme="light", reduced_motion="reduce")
        ctx.add_init_script(HIDE)
        page = ctx.new_page()

        # 1. Intake
        page.goto(args.base)
        page.get_by_placeholder("Company name, e.g. Sobha").wait_for()
        settle(page)
        page.screenshot(path=OUT / "01-intake.png")

        # 2. A live run (demo mode streams real stage events with fake model calls)
        page.get_by_placeholder("Company name, e.g. Sobha").fill(args.company)
        page.keyboard.press("Enter")
        page.wait_for_selector("text=Opportunities", timeout=20_000)
        page.wait_for_timeout(24_000)
        page.screenshot(path=OUT / "02-run-timeline.png")

        # 3. The report opens by itself when the run finishes
        page.wait_for_url(f"**/?run={slug}**", timeout=90_000)
        page.wait_for_selector("h1")
        settle(page, 1200)
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=OUT / "03-report.png")

        # 4. Ranked opportunities with the winner expanded
        page.evaluate("document.documentElement.style.scrollBehavior='auto';"
                      "window.scrollTo(0, document.getElementById('opportunities').offsetTop - 70)")
        settle(page)
        page.screenshot(path=OUT / "04-opportunities.png")

        # 5. The A4 pitch preview (identical to the PDF export)
        page.evaluate("window.scrollTo(0, document.getElementById('ceo-pitch').offsetTop - 70)")
        page.wait_for_selector("iframe[title^='One-page pitch']", timeout=30_000)
        settle(page, 1500)
        page.screenshot(path=OUT / "05-ceo-pitch.png")

        # 6. How it works: the pipeline map with the verifier selected
        page.goto(f"{args.base}/?view=how-it-works")
        page.get_by_role("button", name=re.compile(r"^Verifier")).click()
        settle(page, 900)
        page.screenshot(path=OUT / "06-how-it-works.png")

        # 7. Phone
        phone = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True,
                                    has_touch=True, color_scheme="light", reduced_motion="reduce")
        phone.add_init_script(HIDE)
        mp = phone.new_page()
        mp.goto(f"{args.base}/?run={slug}")
        mp.wait_for_selector("h1")
        settle(mp, 1200)
        mp.screenshot(path=OUT / "07-phone.png")

        # 8. Dark mode
        dark = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2,
                                   color_scheme="dark", reduced_motion="reduce")
        dark.add_init_script(HIDE)
        dp = dark.new_page()
        dp.goto(f"{args.base}/?run={slug}")
        dp.wait_for_selector("h1")
        settle(dp, 1200)
        dp.screenshot(path=OUT / "08-dark.png")
        browser.close()
    for f in sorted(OUT.glob("*.png")):
        print(f.relative_to(ROOT), f"{f.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
