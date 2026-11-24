"""CEO voice, in plain Python (no LLM call).

1. Quotes must be verbatim: every leader statement the fact extractor returns is kept only if its
   `quote` appears word for word in the cached source text (after normalizing whitespace, case,
   curly quotes and dashes). A paraphrased or invented quote is dropped.
2. Stated priorities: the newest verified statements by a current top leader (CEO, MD, chair, founder).
3. The pitch opens on one stated priority, quoting it and citing its source. With no verifiable
   statement it opens on the newest cited fact instead, and the report says no CEO statements were found.
"""
from __future__ import annotations

import re
from datetime import date

from utils.dates import months_old, parse_as_of
from utils.schemas import BusinessProfile, LeaderStatement, PitchOpening, SourceDoc, StatedPriority

MIN_QUOTE_WORDS = 5
PRIORITY_MAX_MONTHS = 12
MAX_PRIORITIES = 3
TOP_ROLES = re.compile(r"\b(ceo|chief executive|managing director|\bmd\b|chair|founder|president|executive director)",
                       re.I)
_QUOTED = re.compile(r"[\"“”]([^\"“”]{12,}?)[\"“”]")


def normalize(text: str) -> str:
    t = (text or "").lower()
    t = t.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", " ": " "}))
    t = re.sub(r"-\s*\n\s*", "", t)        # words hyphenated across PDF lines
    t = re.sub(r"\s+", " ", t)
    return t.strip().strip('"\'').strip()


def is_verbatim(quote: str, source_text: str) -> bool:
    q = normalize(quote).rstrip(".,;:")
    return len(q.split()) >= MIN_QUOTE_WORDS and q in normalize(source_text)


def verify_statements(statements: list[LeaderStatement], source_text: str) -> tuple[list[LeaderStatement], int]:
    """Keep only quotes found word for word in the source; return (kept, number dropped)."""
    kept = [s for s in statements if is_verbatim(s.quote, source_text)]
    return kept, len(statements) - len(kept)


def _last_name(name: str) -> str:
    parts = re.sub(r"[^\w\s.-]", " ", name or "").split()
    return parts[-1].lower() if parts else ""


def stated_priorities(profile: BusinessProfile, today: date | None = None,
                      limit: int = MAX_PRIORITIES) -> list[StatedPriority]:
    """Newest verified statements by a current top leader, at most one per topic."""
    today = today or date.today()
    by_source = {s.source_id: s for s in profile.sources_index}
    current = {_last_name(entry.split("—")[0]) for entry in profile.leadership}
    out: list[StatedPriority] = []
    for st in profile.leader_statements:
        src: SourceDoc | None = by_source.get(st.get("source_id", ""))
        if not src or not st.get("quote"):
            continue
        if not TOP_ROLES.search(st.get("role", "")):
            continue
        # The speaker must still be in charge: if current leadership is known, they must be in it.
        if current and _last_name(st.get("speaker", "")) not in current:
            continue
        when = parse_as_of(st.get("date")) or src.published or (
            src.retrieved if src.source_type in ("company", "investor") else None)
        age = months_old(when, today)
        if age is None or age > PRIORITY_MAX_MONTHS:
            continue
        out.append(StatedPriority(topic=st.get("topic", ""), quote=st["quote"].strip(), speaker=st.get("speaker", ""),
                                  role=st.get("role", ""), date=when, source_id=src.source_id, source_title=src.title,
                                  url=src.url))
    out.sort(key=lambda p: p.date or "", reverse=True)
    seen, unique = set(), []
    for p in out:
        key = normalize(p.topic) or normalize(p.quote)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique[:limit]


def _when(iso: str | None) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def pitch_opening(profile: BusinessProfile, addressed_to: str = "") -> PitchOpening | None:
    """The first line of the pitch: a stated priority if one is verifiable, else the newest cited fact."""
    if profile.stated_priorities:
        p = profile.stated_priorities[0]
        you = bool(_last_name(p.speaker)) and _last_name(p.speaker) in addressed_to.lower()
        who = "you" if you else p.speaker
        where = f"in {p.source_title}" if p.source_title else "publicly"
        when = f" ({_when(p.date)})" if p.date else ""
        return PitchOpening(kind="stated_priority", text=f'{where[0].upper()}{where[1:]}{when}, {who} said: "{p.quote}"',
                            source_id=p.source_id, quote=p.quote, speaker=p.speaker, date=p.date)
    docs = {s.source_id: s for s in profile.sources_index if s.kind != "snippet"}
    candidates = [f for f in profile.facts if f.source_id in docs and not f.superseded_by and f.as_of]
    if not candidates:
        return None
    # Prefer figures and announcements over generic statements; newest first.
    f = max(candidates, key=lambda x: (x.as_of or "", bool(x.metric)))
    return PitchOpening(kind="newest_fact", text=f.statement.rstrip(".") + f" ({_when(f.as_of)}).",
                        source_id=f.fact_id, date=f.as_of)


def invented_quotes(text: str, profile: BusinessProfile) -> list[str]:
    """Quoted passages in generated text that aren't a verified statement (or part of one)."""
    verified = [normalize(s.get("quote", "")) for s in profile.leader_statements]
    bad = []
    for m in _QUOTED.finditer(text or ""):
        q = normalize(m.group(1)).rstrip(".,;:")
        if len(q.split()) >= 4 and not any(q in v for v in verified):
            bad.append(m.group(1))
    return bad
