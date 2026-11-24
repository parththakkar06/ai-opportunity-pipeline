#!/usr/bin/env python3
"""Orchestrator: runs the 4 stages in sequence for one company and writes the 5-section report.

    Stage 1  Researcher                      -> 01_business_profile.json
    Stage 2  Challenge & Reasoning Analyst   -> 02_business_challenges.json
    Stage 3  AI Opportunity Strategist       -> 03_ai_opportunities.json, 03_winning_strategy.{json,md}
    Stage 4  CEO Pitch Builder               -> 04_ceo_pitch.{md,json}, 04_prototype.html
    Report   (Python, no LLM)                -> 05_assessment_report.{json,md}

    python run_pipeline.py "Sobha" --url sobha.com
    python run_pipeline.py "Acme Dental" --context "family dentist in Austin, TX"
    python run_pipeline.py "Sobha" --from-step 3            # reuse saved stages 1-2, rerun 3 and 4
    python run_pipeline.py "Sobha" --no-prototype           # skip the HTML prototype (faster)
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from agents import STAGES
from agents.base import META_JSON, REQUIRED_INPUTS, PipelineContext
from agents.report import write_report
from utils.config import ConfigError, Settings, load_settings
from utils.console import PipelineUI
from utils.costs import CostTracker
from utils.io import HandoffError, slugify, write_json
from utils.llm import LLMClient, LLMError, build_llm
from utils.schemas import RunMeta
from utils.search import WebResearch


class PipelineError(RuntimeError):
    pass


@dataclass
class PipelineResult:
    out_dir: Path
    files: list[Path] = field(default_factory=list)
    tracker: CostTracker = field(default_factory=CostTracker)


def run_pipeline(
    business_name: str,
    *,
    url: str | None = None,
    context: str | None = None,
    from_step: int = 1,
    provider: str | None = None,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    research: WebResearch | None = None,
    outputs_root: Path | None = None,
    ui: PipelineUI | None = None,
    build_prototype: bool | None = None,
    slug: str | None = None,
    refresh: bool = False,
) -> PipelineResult:
    """Run the pipeline. Every dependency can be injected, which is how the offline test works."""
    if not business_name.strip():
        raise PipelineError("Business name must not be empty.")
    if from_step not in REQUIRED_INPUTS:
        raise PipelineError("--from-step must be 1, 2, 3 or 4.")

    ui = ui or PipelineUI()
    settings = settings or load_settings(provider)
    if build_prototype is not None:
        settings.build_prototype = build_prototype
    if refresh:
        settings.refresh_cache = True
    tracker = llm.tracker if llm else CostTracker()
    llm = llm or build_llm(settings, tracker)
    llm.notify = ui.note          # e.g. "model X busy; switching to Y" shows up in the CLI and the web tracker
    research = research or WebResearch.from_settings(settings)

    # `slug` lets a caller resume an existing run folder whose name differs from the company name typed now.
    if slug is not None and slugify(slug) != slug:
        raise PipelineError(f"Invalid run folder name {slug!r}.")
    out_dir = (outputs_root or settings.outputs_dir) / (slug or slugify(business_name))
    out_dir.mkdir(parents=True, exist_ok=True)

    missing = [name for name in REQUIRED_INPUTS[from_step] if not (out_dir / name).exists()]
    if missing:
        raise PipelineError(
            f"Cannot start at stage {from_step}: missing {', '.join(missing)} in {out_dir}. "
            "Run from an earlier step first."
        )

    ui.banner(business_name, settings.provider, settings.model, research.provider_names, out_dir)
    meta = RunMeta(
        business_name=business_name, slug=out_dir.name, url=url, context=context,
        provider=settings.provider, model=settings.model, builder_model=settings.builder_model,
        from_step=from_step, started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    ctx = PipelineContext(
        business_name=business_name, out_dir=out_dir, settings=settings, llm=llm, research=research,
        url=url, context=context, note=ui.note,
    )

    result = PipelineResult(out_dir=out_dir, tracker=tracker)
    started = time.perf_counter()
    for stage, stage_title, agent_classes in STAGES:
        if stage < from_step:
            ui.skipped(stage, stage_title)
            continue
        ui.stage_start(stage, stage_title)
        tracker.stage = stage
        stage_t0 = time.perf_counter()
        for agent_cls in agent_classes:
            agent = agent_cls(ctx)
            t0 = time.perf_counter()
            with ui.agent(stage, agent.title) as status:
                ctx.status = status
                files = agent.run()
            ui.agent_done(agent.title, time.perf_counter() - t0, tracker.for_agent(agent.key), files)
            result.files.extend(files)
        stage_seconds = time.perf_counter() - stage_t0
        ui.stage_done(stage, stage_title, stage_seconds)
        st = tracker.for_stage(stage)
        meta.stages[str(stage)] = {"title": stage_title, "input_tokens": st.input_tokens,
                                   "output_tokens": st.output_tokens, "calls": st.calls,
                                   "seconds": round(stage_seconds, 1)}

    total = tracker.total()
    meta.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta.total_input_tokens, meta.total_output_tokens = total.input_tokens, total.output_tokens
    meta.total_cost_usd = round(total.cost_usd, 4) if total.cost_usd is not None else None
    meta.search_providers_used = ctx.search_providers_used
    meta.elapsed_seconds = round(time.perf_counter() - started, 1)
    meta.research = ctx.research_stats
    result.files.append(write_json(out_dir / META_JSON, meta))
    result.files.extend(write_report(out_dir))   # the 5-section assessment report

    ui.summary(out_dir, result.files, tracker, time.perf_counter() - started)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Research a business, find its best AI opportunity, and build a pitch + prototype.")
    p.add_argument("business", help='Business name, e.g. "Acme Dental"')
    p.add_argument("--url", help="The business's website, to lock onto the right company (e.g. acmedental.com)")
    p.add_argument("--context", help='Extra disambiguating context, e.g. "family dentist in Austin, TX"')
    p.add_argument("--from-step", type=int, default=1, choices=[1, 2, 3, 4],
                   help="Resume from this stage, reusing saved outputs of earlier stages")
    p.add_argument("--no-prototype", action="store_true", help="Skip the HTML prototype in stage 4 (faster)")
    p.add_argument("--refresh", action="store_true", help="Ignore the research cache and fetch everything again")
    p.add_argument("--provider", choices=["gemini", "openai", "openrouter"], help="Override LLM_PROVIDER from .env")
    p.add_argument("--outputs-dir", type=Path, help="Where to write outputs (default: ./outputs)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ui = PipelineUI()
    try:
        run_pipeline(args.business, url=args.url, context=args.context, from_step=args.from_step,
                     provider=args.provider, outputs_root=args.outputs_dir, ui=ui,
                     build_prototype=False if args.no_prototype else None, refresh=args.refresh)
        return 0
    except (ConfigError, PipelineError, HandoffError, LLMError) as exc:
        ui.error(str(exc))
        return 1
    except KeyboardInterrupt:
        ui.warn("Interrupted. Completed steps are saved; resume with --from-step.")
        return 130
    except Exception as exc:  # noqa: BLE001 - last-resort friendly message (auth errors, network, etc.)
        ui.error(f"{type(exc).__name__}: {exc}\n\nCompleted steps are saved; fix the issue and resume with --from-step.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
