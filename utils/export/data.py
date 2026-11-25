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


PAPER, SHEET = "#FBFAF7", "#FFFFFF"
MIN_CONTRAST = 4.5


def _rgb(h: str) -> tuple[float, float, float]:
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def _luminance(h: str) -> float:
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in _rgb(h)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _hex(value: str | None) -> str:
    """The brand colour, darkened until it reads at 4.5:1 on paper and white (same rule as the web app,
    frontend/src/lib/brand.ts). Near-grey or missing colours fall back to ink blue."""
    if not value or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return INK_BLUE
    r, g, b = _rgb(value)
    if max(r, g, b) - min(r, g, b) < 0.12:      # too grey to act as an accent
        return INK_BLUE
    colour = value.upper()
    for _ in range(40):
        if min(contrast(colour, PAPER), contrast(colour, SHEET)) >= MIN_CONTRAST:
            return colour
        colour = "#" + "".join(f"{max(0, int(round(x * 255 * 0.94))):02X}" for x in _rgb(colour))
    return INK_BLUE


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
