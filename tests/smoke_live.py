#!/usr/bin/env python3
"""Live end-to-end smoke test: real LLM, real web search. Costs real API credits.

Needs GEMINI_API_KEY in .env (or OPENAI_API_KEY + OPENAI_MODEL with --provider openai).

    python tests/smoke_live.py                                  # default business
    python tests/smoke_live.py "Blue Bottle Coffee" --url bluebottlecoffee.com
    python tests/smoke_live.py "Acme Dental" --provider openai

Exits 0 only if every deliverable exists and every JSON handoff validates.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rich.console import Console  # noqa: E402

from agents.base import (  # noqa: E402
    CHALLENGES_JSON, META_JSON, OPPORTUNITIES_JSON, PITCH_MD, PROFILE_JSON, PROTOTYPE_HTML, REPORT_MD,
    STRATEGY_JSON, STRATEGY_MD,
)
from run_pipeline import run_pipeline  # noqa: E402
from utils.config import load_settings  # noqa: E402
from utils.costs import fmt_cost  # noqa: E402
from utils.schemas import AIOpportunities, BusinessChallenges, BusinessProfile, RunMeta, WinningStrategy  # noqa: E402

console = Console()


def preflight(provider: str) -> list[str]:
    problems = []
    if provider == "gemini" and not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        problems.append("GEMINI_API_KEY is not set (add it to .env).")
    if provider == "openrouter" and not os.getenv("OPENROUTER_API_KEY"):
        problems.append("OPENROUTER_API_KEY is not set (add it to .env).")
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            problems.append("OPENAI_API_KEY is not set (add it to .env).")
        if not os.getenv("OPENAI_MODEL"):
            problems.append("OPENAI_MODEL is not set (add it to .env).")
    return problems


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("business", nargs="?", default="Blue Bottle Coffee")
    p.add_argument("--url", default=None)
    p.add_argument("--context", default=None)
    p.add_argument("--provider", choices=["gemini", "openai", "openrouter"], default=None)
    p.add_argument("--no-prototype", action="store_true", help="skip the HTML prototype (faster, cheaper)")
    args = p.parse_args()
    if args.business == "Blue Bottle Coffee" and args.url is None:
        args.url = "bluebottlecoffee.com"

    settings = load_settings(args.provider)
    problems = preflight(settings.provider)
    if problems:
        for msg in problems:
            console.print(f"[red]✗ {msg}[/red]")
        return 2
    search = "Tavily" if settings.tavily_api_key else "Serper" if settings.serper_api_key else "DuckDuckGo (no key)"
    console.print(f"[bold]Live smoke test[/bold] · {settings.provider} · {settings.model} · search: {search}")

    if args.no_prototype:
        settings.build_prototype = False
    result = run_pipeline(args.business, url=args.url, context=args.context, settings=settings)
    out = result.out_dir

    checks: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            detail = fn() or ""
            checks.append((name, True, str(detail)))
        except Exception as exc:  # noqa: BLE001
            checks.append((name, False, f"{type(exc).__name__}: {exc}"))

    check(PROFILE_JSON, lambda: f"data_quality={BusinessProfile.model_validate_json((out / PROFILE_JSON).read_text()).data_quality}")
    check(CHALLENGES_JSON, lambda: f"{len(BusinessChallenges.model_validate_json((out / CHALLENGES_JSON).read_text()).challenges)} challenges")
    check(OPPORTUNITIES_JSON, lambda: f"{len(AIOpportunities.model_validate_json((out / OPPORTUNITIES_JSON).read_text()).opportunities)} ideas")
    check(STRATEGY_JSON, lambda: f"winner: {WinningStrategy.model_validate_json((out / STRATEGY_JSON).read_text()).winner.title}")

    def md_ok(name: str, *needles: str):
        def _f():
            text = (out / name).read_text()
            missing = [n for n in needles if n not in text]
            assert not missing, f"missing sections: {missing}"
            return f"{len(text):,} chars"
        return _f

    check(STRATEGY_MD, md_ok(STRATEGY_MD, "Executive summary", "Scoreboard"))
    check(PITCH_MD, md_ok(PITCH_MD, "Why we reached out", "What we recommend", "Cold outreach email", "ROI breakdown"))
    check(REPORT_MD, md_ok(REPORT_MD, "## 1. Company Overview", "## 2. Key Business Information",
                           "## 3. Potential Business Challenges", "**Reasoning:**", "## 4. AI Opportunities",
                           "## 5. Personalized CEO Pitch"))

    def html_ok():
        html = (out / PROTOTYPE_HTML).read_text()
        assert html.rstrip().lower().endswith("</html>"), "not a complete document"
        assert "cdn.tailwindcss.com" in html, "Tailwind missing"
        assert "addEventListener" in html or "onclick" in html.lower(), "no interactivity found"
        return f"{len(html):,} chars"

    if settings.build_prototype:
        check(PROTOTYPE_HTML, html_ok)
    check(META_JSON, lambda: f"cost {fmt_cost(RunMeta.model_validate_json((out / META_JSON).read_text()).total_cost_usd)}")

    console.rule("Smoke test results")
    for name, ok, detail in checks:
        console.print(f"{'[green]✓' if ok else '[red]✗'}[/] {name}  [dim]{detail}[/dim]")
    failed = [c for c in checks if not c[1]]
    console.print(f"\n[bold]{'PASS' if not failed else 'FAIL'}[/bold] · outputs in {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
