"""Provenance rules for Stage 1, in plain Python (no LLM), so they are deterministic and testable.

- Every fact gets an id (S3.F7 for documents, R12 for search snippets) and an as-of date.
- Newest source wins: an older fact about the same metric and period type is marked superseded.
- Leadership names survive only with cited evidence from the last 12 months that actually names
  them, and that hasn't been superseded by a newer fact about the same role.
- Figures in the profile that appear nowhere in the evidence are removed (no filling from memory).
- Gaps (missing, stale, low-confidence fields) become at most 4 templated follow-up queries.
"""
from __future__ import annotations

import re
from datetime import date

from utils.dates import months_old, parse_as_of
from utils.schemas import (
    BusinessProfile, BusinessProfileDraft, DocFacts, Fact, FieldEvidence, SourceDoc,
)
from utils.search import Query, SearchResult

LEADERSHIP_MAX_MONTHS = 12
STALE_FINANCIALS_MONTHS = 9
ROLE_METRICS = {"managing_director", "ceo", "chief_executive_officer", "chairman", "cfo", "chief_financial_officer",
                "president", "founder", "executive_director", "whole_time_director"}


# ------------------------------------------------------------------------------------------- facts
def _age(iso: str | None, today: date) -> float:
    """Months since `iso`; undated counts as very old (0 months is a valid age, not 'missing')."""
    age = months_old(iso, today)
    return 99.0 if age is None else age


def _granularity(period: str | None) -> str:
    p = (period or "").upper()
    if re.search(r"\bQ[1-4]|\bH[12]\b|QUARTER", p):
        return "quarter"
    if re.search(r"FY|YEAR|ANNUAL|\b20\d{2}\b", p):
        return "year"
    return "point"


def document_facts(doc: DocFacts, source: SourceDoc) -> list[Fact]:
    """Turn one document's extracted facts into stored facts with ids and resolved dates."""
    out: list[Fact] = []
    doc_date = parse_as_of(doc.document_date) or source.published
    for i, f in enumerate(doc.facts, 1):
        stated = parse_as_of(f.as_of) or parse_as_of(f.period)
        if stated:
            as_of, basis = stated, "stated"
        elif doc_date:
            as_of, basis = doc_date, "published"
        elif source.source_type in ("company", "investor") and source.retrieved:
            as_of, basis = source.retrieved, "retrieved"   # a live company page reflects the present
        else:
            as_of, basis = None, "unknown"
        out.append(Fact(**f.model_dump(exclude={"as_of"}), as_of=as_of, fact_id=f"{source.source_id}.F{i}",
                        source_id=source.source_id, as_of_basis=basis))
    return out


def snippet_sources(results: list[SearchResult], start: int = 1) -> tuple[list[SourceDoc], list[Fact]]:
    """Search snippets become weak, dated evidence with ids R1, R2, …"""
    sources, facts = [], []
    for i, r in enumerate(results, start):
        sid = f"R{i}"
        published = parse_as_of(r.date) or parse_as_of(r.url)
        sources.append(SourceDoc(source_id=sid, url=r.url, title=r.title[:200], source_type="snippet", kind="snippet",
                                 published=published))
        text = f"{r.title}: {r.snippet}".strip()[:400]
        facts.append(Fact(statement=text, fact_id=sid, source_id=sid, as_of=published,
                          as_of_basis="published" if published else "unknown"))
    return sources, facts


def mark_superseded(facts: list[Fact]) -> list[Fact]:
    """Newest source wins: per (metric, period granularity) only the newest dated fact stays current."""
    groups: dict[tuple[str, str], list[Fact]] = {}
    for f in facts:
        if f.metric and f.as_of:
            key = (f.metric.lower(), "role" if f.metric.lower() in ROLE_METRICS else _granularity(f.period))
            groups.setdefault(key, []).append(f)
    for items in groups.values():
        items.sort(key=lambda f: f.as_of or "", reverse=True)
        newest = items[0]
        for older in items[1:]:
            if older.as_of < newest.as_of:
                older.superseded_by = newest.fact_id
    return facts


def format_evidence(sources: list[SourceDoc], facts: list[Fact], homepage_block: str = "",
                    cap: int = 30_000) -> str:
    """The evidence pack main agents read: facts only (never raw page text), newest first, capped."""
    by_source: dict[str, list[Fact]] = {}
    for f in facts:
        by_source.setdefault(f.source_id, []).append(f)
    parts: list[str] = []
    docs = [s for s in sources if s.kind != "snippet"]
    snippets = [s for s in sources if s.kind == "snippet"]
    if docs:
        parts.append("## Facts from full documents")
    for s in docs:
        parts.append(f"[{s.source_id}] {s.source_type}/{s.kind} · {s.published or 'undated'} · {s.title} · {s.url}")
        for f in sorted(by_source.get(s.source_id, []), key=lambda x: x.as_of or "", reverse=True):
            extra = "; ".join(x for x in (f.value, f.period) if x)
            flag = f" [superseded by {f.superseded_by}]" if f.superseded_by else ""
            parts.append(f"  {f.fact_id} [{f.as_of or 'undated'}] {f.statement}{f' ({extra})' if extra else ''}{flag}")
    if snippets:
        parts.append("## Search snippets (weaker evidence)")
        for s in snippets:
            for f in by_source.get(s.source_id, []):
                parts.append(f"  {f.fact_id} [{f.as_of or 'undated'}] {f.statement} · {s.url}")
    if homepage_block:
        parts.append(homepage_block)
    text = "\n".join(parts)
    return text if len(text) <= cap else text[:cap] + "\n[evidence truncated]"


# ------------------------------------------------------------------------------------------- validation
_PERIOD_TOKENS = re.compile(r"\b(?:Q[1-4]\s*)?FY\s*'?\d{2,4}(?:\s*[-–/]\s*\d{2,4})?\b|\bQ[1-4]\b|\bH[12]\b", re.I)


def _numbers(text: str) -> list[str]:
    stripped = _PERIOD_TOKENS.sub(" ", text)
    nums = [n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*\.?\d*", stripped)]
    return [n for n in nums if len(n.replace(".", "")) >= 2 and not re.fullmatch(r"(19|20)\d{2}", n)]


def _supported(value: str, corpus: str) -> bool:
    nums = _numbers(value)
    return not nums or any(n in corpus for n in nums)


def _corpus(facts: list[Fact]) -> str:
    return " ".join(f"{f.statement} {f.value or ''}" for f in facts).replace(",", "")


def validate_profile(draft: BusinessProfileDraft, sources: list[SourceDoc], facts: list[Fact],
                     today: date | None = None) -> BusinessProfile:
    today = today or date.today()
    by_id = {f.fact_id: f for f in facts}
    warnings: list[str] = []
    assumptions = list(draft.assumptions)
    corpus = _corpus(facts)

    # 1. Evidence ids must exist; citing a superseded fact is flagged.
    evidence: list[FieldEvidence] = []
    for fe in draft.field_evidence:
        valid = [i for i in fe.evidence if i in by_id]
        if len(valid) < len(fe.evidence):
            warnings.append(f"{fe.field}: ignored unknown evidence ids {sorted(set(fe.evidence) - set(valid))}")
        for i in valid:
            if by_id[i].superseded_by:
                warnings.append(f"{fe.field}: cites {i}, superseded by newer {by_id[i].superseded_by}")
        evidence.append(FieldEvidence(field=fe.field, evidence=valid))

    # 2. Leadership: named in cited, current (≤12 months) evidence and not superseded.
    leaders, leadership = [], []
    for leader in draft.leaders:
        cited = [by_id[i] for i in leader.evidence if i in by_id]
        last_name = leader.name.strip().split()[-1].lower() if leader.name.strip() else ""
        naming = [f for f in cited if last_name and last_name in f.statement.lower()]
        current = [f for f in naming if f.as_of_basis != "unknown" and _age(f.as_of, today) <= LEADERSHIP_MAX_MONTHS]
        replaced = [f for f in naming if f.superseded_by]
        if not naming:
            reason = "no cited fact names this person"
        elif replaced and len(replaced) == len(naming):
            newer = by_id.get(replaced[0].superseded_by)
            reason = f"superseded by newer evidence {replaced[0].superseded_by}" + (f" ({newer.statement[:90]})" if newer else "")
        elif not current:
            dates = ", ".join(sorted({f.as_of or 'undated' for f in naming}))
            reason = f"evidence is older than {LEADERSHIP_MAX_MONTHS} months or undated ({dates})"
        else:
            leaders.append(leader.model_copy(update={"evidence": [f.fact_id for f in current]}))
            leadership.append(f"{leader.name} — {leader.role}")
            continue
        warnings.append(f"Leader '{leader.name}' ({leader.role}) dropped: {reason}")
        assumptions.append(f"{leader.role}: current holder unknown (no evidence from the last {LEADERSHIP_MAX_MONTHS} months).")

    # 3. Figures must appear in the evidence; otherwise they came from somewhere else and are removed.
    scale = draft.scale.model_copy()
    for field in ("revenue", "projects_or_portfolio", "employees"):
        value = getattr(scale, field)
        if value and not _supported(value, corpus):
            setattr(scale, field, None)
            warnings.append(f"scale.{field}: removed '{value}' (figure not found in the evidence)")
            assumptions.append(f"scale.{field}: no supported figure in the evidence.")
    kept_metrics = []
    for m in scale.other_metrics:
        if _supported(m, corpus):
            kept_metrics.append(m)
        else:
            warnings.append(f"scale.other_metrics: removed '{m}' (figure not found in the evidence)")
    scale.other_metrics = kept_metrics

    used = {f.source_id for fe in evidence for i in fe.evidence if (f := by_id.get(i))}
    used |= {by_id[i].source_id for leader in leaders for i in leader.evidence}
    source_urls = [s.url for s in sources if s.source_id in used] or [s.url for s in sources if s.kind != "snippet"]

    return BusinessProfile(
        **draft.model_dump(exclude={"scale", "leaders", "field_evidence", "assumptions"}),
        scale=scale, leaders=leaders, field_evidence=evidence, assumptions=list(dict.fromkeys(assumptions)),
        leadership=leadership, sources=source_urls, sources_index=sources, facts=facts,
        provenance_warnings=warnings,
    )


# ------------------------------------------------------------------------------------------- gaps
def detect_gaps(profile: BusinessProfile, today: date | None = None) -> list[str]:
    """Fields worth one follow-up search round: missing, stale or low-confidence."""
    today = today or date.today()
    gaps: list[str] = []
    if not profile.leadership:
        gaps.append("leadership")
    fin = [f for f in profile.facts if (f.metric or "").lower() in {"revenue", "sales_bookings", "collections", "net_profit"}
           and not f.superseded_by]
    newest = max((f.as_of for f in fin if f.as_of), default=None)
    if not profile.scale.revenue or newest is None or _age(newest, today) > STALE_FINANCIALS_MONTHS:
        gaps.append("financials")
    if not profile.recent_news:
        gaps.append("recent_news")
    if not profile.major_projects:
        gaps.append("projects")
    low = {fc.field.lower() for fc in profile.field_confidence if fc.confidence == "low"}
    if any("expansion" in f or "pipeline" in f for f in low) or not profile.expansion_plans:
        gaps.append("expansion")
    return gaps


def gap_queries(name: str, gaps: list[str], year: int | None = None, limit: int = 4) -> list[Query]:
    year = year or date.today().year
    templates = {
        "leadership": Query(f'"{name}" managing director OR CEO appointed {year}', "news"),
        "financials": Query(f'"{name}" quarterly results {year} sales bookings revenue'),
        "recent_news": Query(f"{name} news {year}", "news"),
        "projects": Query(f'"{name}" new project launch {year} RERA'),
        "expansion": Query(f'"{name}" expansion plans {year} land acquisition'),
    }
    return [templates[g] for g in gaps if g in templates][:limit]
