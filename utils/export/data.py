"""Everything an export needs, loaded from the saved run (no LLM calls)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from agents.base import PITCH_JSON, PROFILE_JSON, find_file
from agents.report import build_report
from utils.schemas import AssessmentReport, BusinessProfile, ROISummary

INK_BLUE = "#1F3A6E"


@dataclass
class ExportData:
    out_dir: Path
    report: AssessmentReport
    profile: BusinessProfile
    roi: ROISummary | None
    accent: str

    @property
    def slug(self) -> str:
        return self.out_dir.name

    def marks(self, node_id: str) -> list[int]:
        if not self.report.trace:
            return []
        node = next((n for n in self.report.trace.nodes if n.id == node_id), None)
        return node.citations if node else []

    def lines(self, field: str) -> list[tuple[str, list[int]]]:
        """Trace lines for a pitch field, with their citation numbers."""
        if not self.report.trace:
            return []
        return [(n.label, n.citations) for n in self.report.trace.nodes if n.field == field]


def _hex(value: str | None) -> str:
    return value if value and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else INK_BLUE


def load(out_dir: Path) -> ExportData:
    report = build_report(out_dir)
    profile = BusinessProfile.model_validate_json(find_file(out_dir, PROFILE_JSON).read_text(encoding="utf-8"))
    roi = None
    pitch = find_file(out_dir, PITCH_JSON)
    if pitch:
        raw = json.loads(pitch.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and raw.get("roi"):
            roi = ROISummary.model_validate(raw["roi"])
    return ExportData(out_dir, report, profile, roi, _hex(profile.brand.primary_color_hex))


def usd(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"${x / 1_000_000:.1f}M" if abs(x) >= 1_000_000 else f"${x:,.0f}"
