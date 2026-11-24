"""Shared agent plumbing: context object, file names, prompt loading."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from utils.config import Settings, load_prompt
from utils.llm import LLMClient
from utils.search import WebResearch

# Handoff file names, in pipeline order (the number is the stage that writes it).
PROFILE_JSON = "01_business_profile.json"
CHALLENGES_JSON = "02_business_challenges.json"
OPPORTUNITIES_JSON = "03_ai_opportunities.json"
STRATEGY_JSON = "03_winning_strategy.json"
STRATEGY_MD = "03_winning_strategy.md"
PITCH_MD = "04_ceo_pitch.md"
PITCH_JSON = "04_ceo_pitch.json"
PROTOTYPE_HTML = "04_prototype.html"
REPORT_JSON = "05_assessment_report.json"
REPORT_MD = "05_assessment_report.md"
META_JSON = "00_run_meta.json"

# Names used by runs saved before the 5-section layout; read-only fallbacks.
LEGACY_NAMES: dict[str, list[str]] = {
    OPPORTUNITIES_JSON: ["02_ai_opportunities.json"],
    PITCH_JSON: ["04_executive_pitch.json"],
    PITCH_MD: ["04_executive_pitch.md"],
}

# The 4 user-facing stages. Stage 3 runs two agents (ideation, then rubric scoring).
STAGE_TITLES: dict[int, str] = {
    1: "Researcher",
    2: "Challenge & Reasoning Analyst",
    3: "AI Opportunity Strategist",
    4: "CEO Pitch Builder",
}

# Which earlier files each stage needs when you resume with --from-step.
REQUIRED_INPUTS: dict[int, list[str]] = {
    1: [],
    2: [PROFILE_JSON],
    3: [PROFILE_JSON, CHALLENGES_JSON],
    4: [PROFILE_JSON, CHALLENGES_JSON, STRATEGY_JSON],
}


def find_file(out_dir: Path, name: str) -> Path | None:
    """Return the current or legacy path of a handoff file, if it exists."""
    for candidate in [name, *LEGACY_NAMES.get(name, [])]:
        path = out_dir / candidate
        if path.exists():
            return path
    return None


@dataclass
class PipelineContext:
    business_name: str
    out_dir: Path
    settings: Settings
    llm: LLMClient
    research: WebResearch
    url: str | None = None
    context: str | None = None
    status: Callable[[str], None] = lambda _msg: None
    note: Callable[[str], None] = lambda _msg: None
    search_providers_used: list[str] = field(default_factory=list)

    def path(self, name: str) -> Path:
        return self.out_dir / name


class Agent:
    stage: int = 0              # 1-4, the user-facing stage this agent belongs to
    key: str = "agent"          # used for cost tracking
    title: str = "Agent"

    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx

    def prompt(self, filename: str) -> str:
        return load_prompt(filename)

    def run(self) -> list[Path]:
        raise NotImplementedError


def _plain(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def as_json(model: BaseModel | dict | list) -> str:
    return json.dumps(_plain(model), indent=2, ensure_ascii=False)
