"""Turn the date-ish strings found in filings, news and snippets into comparable ISO dates.

Indian fiscal years run April–March, so "FY26" ends 2026-03-31 and "Q1 FY27" ends 2026-06-30.
Every function returns an ISO date string (YYYY-MM-DD) or None; callers compare strings directly.
"""
from __future__ import annotations

import re
from datetime import date, datetime

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_QUARTER_END = {1: (0, 6, 30), 2: (0, 9, 30), 3: (0, 12, 31), 4: (1, 3, 31)}  # (year offset from FY start, month, day)


def _fy_year(token: str) -> int | None:
    """'26' -> 2026, '2026' -> 2026, '2025-26' -> 2026."""
    token = token.strip()
    m = re.fullmatch(r"(\d{4})\s*[-–/]\s*(\d{2,4})", token)
    if m:
        end = m.group(2)
        return int(end) if len(end) == 4 else int(m.group(1)[:2] + end)
    if re.fullmatch(r"\d{4}", token):
        return int(token)
    if re.fullmatch(r"\d{2}", token):
        return 2000 + int(token)
    return None


def _iso(y: int, mo: int, d: int) -> str | None:
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_as_of(text: str | None) -> str | None:
    """Best-effort: the most specific date or period end mentioned in `text`."""
    if not text:
        return None
    t = str(text)
    # ISO / numeric: 2026-05-12, 2026/05/12
    m = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)", t)
    if m:
        return _iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # 12 May 2026 / May 12, 2026
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*\.?,?\s+(20\d{2})\b", t)
    if m and m.group(2).lower()[:3] in MONTHS:
        return _iso(int(m.group(3)), MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
    m = re.search(r"\b([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(20\d{2})\b", t)
    if m and m.group(1).lower()[:3] in MONTHS:
        return _iso(int(m.group(3)), MONTHS[m.group(1).lower()[:3]], int(m.group(2)))
    # Quarter of a fiscal year: Q1 FY27, Q3FY2026, Q2 FY 2025-26
    m = re.search(r"\bQ([1-4])\s*[-' ]?\s*FY\s*'?(\d{4}\s*[-–/]\s*\d{2,4}|\d{2,4})\b", t, re.I)
    if m:
        fy_end = _fy_year(m.group(2))
        if fy_end:
            off, mo, d = _QUARTER_END[int(m.group(1))]
            return _iso(fy_end - 1 + off, mo, d)
    # Fiscal year: FY26, FY2026, FY 2025-26
    m = re.search(r"\bFY\s*'?(\d{4}\s*[-–/]\s*\d{2,4}|\d{2,4})\b", t, re.I)
    if m:
        fy_end = _fy_year(m.group(1))
        if fy_end:
            return _iso(fy_end, 3, 31)
    # Month Year: May 2026
    m = re.search(r"\b([A-Za-z]{3})[a-z]*\.?\s+(20\d{2})\b", t)
    if m and m.group(1).lower()[:3] in MONTHS:
        mo = MONTHS[m.group(1).lower()[:3]]
        return _iso(int(m.group(2)), mo, 28)
    # Year in a URL path: /2026/05/ or /2026/
    m = re.search(r"/(20\d{2})/(\d{1,2})/", t)
    if m:
        return _iso(int(m.group(1)), int(m.group(2)), 1)
    m = re.search(r"\b(20[12]\d)\b", t)
    if m:
        # A bare year means "some time that year"; never date it in the future.
        return min(_iso(int(m.group(1)), 12, 31), date.today().isoformat())
    return None


def months_old(iso: str | None, today: date | None = None) -> float | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso).date()
    except ValueError:
        return None
    today = today or date.today()
    return (today - d).days / 30.44
