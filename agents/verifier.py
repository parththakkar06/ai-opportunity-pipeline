"""Pitch verifier: runs in Stage 4 after the pitch is drafted and before anything is written.

Python first (no LLM): every person name, figure and fiscal period in the pitch is matched against
the profile's dated facts and verified CEO statements.
- names that aren't current, evidenced leaders are replaced with the role title;
- figures matching only superseded facts are flagged "stale" (a newer figure exists);
- figures inside projections or the ROI model are "estimates", not factual claims;
- anything still unresolved goes to at most ONE cheap-model call (yes / no / partial);
- unsupported figures are removed from the factual paragraphs and flagged everywhere else.
The result is 04_verification.json with each claim, its status, evidence and action, plus a pass rate.
"""
from __future__ import annotations

import re
from typing import Any

from agents.provenance import _granularity
from utils.dates import parse_as_of
from utils.schemas import (
    BusinessProfile, ClaimVerdicts, ExecutivePitchDraft, Fact, VerificationReport, VerifiedClaim,
)

MAX_LLM_CLAIMS = 20
FACTUAL_FIELDS = {"why_we_reached_out", "opportunities_identified.evidence"}
HONORIFIC = r"(?:Mr|Ms|Mrs|Dr|Shri|Smt|Sri)\.?\s+"
ROLE_WORDS = {"managing", "director", "ceo", "chief", "executive", "officer", "chairman", "chairperson", "chair",
              "founder", "co-founder", "president", "md", "cfo", "coo", "cto", "head", "team", "leadership", "board",
              "the", "and", "&", "of", "vice", "whole-time", "whole", "time", "group", "joint", "partner", "owner",
              "principal", "dear", "sir", "madam"}
PROJECTION = re.compile(r"\b(could|would|can|will|may|might|expect\w*|estimat\w*|project\w*|potential\w*|up to|aim\w*|"
                        r"target\w*|pilot\w*|forecast\w*|unlock\w*|recover\w*|save[sd]?|saving\w*|payback|roi)\b", re.I)
_UNIT = r"(?:%|per\s?cent|crore|cr\b|lakh|lac\b|mn\b|million|bn\b|billion|k\b|sq\.?\s?ft|square\s+feet|acres|units|" \
        r"homes|apartments|flats|patients|chairs|staff|employees|customers|projects|clinics|locations|stores)"
_CURRENCY = r"(?:₹|rs\.?\s?|inr\s?|\$|usd\s?)"
NUMBER = re.compile(rf"{_CURRENCY}\d[\d,]*(?:\.\d+)?(?:\s*{_UNIT}){{0,2}}|\d[\d,]*(?:\.\d+)?(?:\s*{_UNIT}){{1,2}}|\b\d{{1,3}}(?:,\d{{2,3}})+\b|"
                    rf"\b\d{{3,}}\b", re.I)
PERIOD = re.compile(r"\bQ[1-4]\s*FY\s*'?\d{2,4}\b|\bH[12]\s*FY\s*'?\d{2,4}\b|\bFY\s*'?\d{2,4}(?:\s*[-–/]\s*\d{2,4})?\b", re.I)
_PERIOD_STRIP = re.compile(r"\b(?:[QH][1-4]\s*)?FY\s*'?\d{2,4}(?:\s*[-–/]\s*\d{2,4})?\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


# ------------------------------------------------------------------------------------------- helpers
def values(text: str) -> list[str]:
    """Numeric values in a claim, normalized (commas and trailing .0 removed). Years are dropped unless money."""
    money = re.search(_CURRENCY, text, re.I)
    out = []
    for n in re.findall(r"\d[\d,]*(?:\.\d+)?", _PERIOD_STRIP.sub(" ", text)):
        n = n.replace(",", "")
        n = n[:-2] if n.endswith(".0") else n
        if not money and re.fullmatch(r"(19|20)\d{2}", n):
            continue
        out.append(n)
    return out


def _number_index(facts: list[Fact]) -> dict[str, list[Fact]]:
    index: dict[str, list[Fact]] = {}
    for f in facts:
        for n in values(f"₹ {f.statement} {f.value or ''}"):   # '₹' so figures that look like years are kept
            index.setdefault(n, []).append(f)
    return index


def _text_fields(d: dict) -> list[tuple[tuple, str, str]]:
    """(path, field label, text) for every free-text pitch field."""
    out = []
    for k in ("addressed_to", "ceo_pitch_title", "why_we_reached_out", "closing", "next_step_cta", "email_subject",
              "email_body", "elevator_pitch"):
        if isinstance(d.get(k), str) and d[k]:
            out.append(((k,), k, d[k]))
    for i, o in enumerate(d.get("opportunities_identified", [])):
        for k in ("title", "evidence"):
            out.append((("opportunities_identified", i, k), f"opportunities_identified.{k}", o.get(k, "")))
    for i, s in enumerate(d.get("recommended_solutions", [])):
        for k in ("name", "what_it_does", "maps_to", "expected_impact"):
            out.append((("recommended_solutions", i, k), f"recommended_solutions.{k}", s.get(k, "")))
    return out


def _get(d: dict, path: tuple) -> Any:
    for p in path:
        d = d[p]
    return d


def _set(d: dict, path: tuple, value: Any) -> None:
    for p in path[:-1]:
        d = d[p]
    d[path[-1]] = value


def _sentence_of(text: str, start: int) -> str:
    pos = 0
    for s in _SENTENCE.split(text):
        idx = text.find(s, pos)
        if idx <= start < idx + len(s) + 1:
            return s.strip()
        pos = idx + len(s)
    return text.strip()


def _last(name: str) -> str:
    parts = re.sub(HONORIFIC, "", name).replace(".", " ").split()
    return parts[-1].lower() if parts else ""


def addressed_person(addressed_to: str) -> str | None:
    """'Mr. Francis Alfred, Managing Director' -> 'Francis Alfred'; 'Managing Director & CEO' -> None."""
    head = re.sub(rf"^\s*(?:Dear\s+)?{HONORIFIC}", "", addressed_to.split(",")[0].strip()).strip()
    words = re.findall(r"[A-Za-z][\w.'-]*", head)
    names = [w for w in words if w[0].isupper() and w.lower().strip(".") not in ROLE_WORDS]
    return head if names and len(names) >= 1 and not all(w.lower() in ROLE_WORDS for w in words) else None


def _roi_values(draft: ExecutivePitchDraft) -> set[str]:
    texts = [a.value for a in draft.roi_assumptions] + [li.calculation for li in draft.roi_line_items]
    nums = [draft.implementation_cost_usd_low, draft.implementation_cost_usd_high, draft.annual_running_cost_usd]
    nums += [x for li in draft.roi_line_items for x in (li.annual_value_usd_low, li.annual_value_usd_high)]
    out = {v for t in texts for v in values(f"₹ {t}")}
    for x in nums:
        out |= {f"{x:.0f}", f"{x / 1000:.0f}", f"{x / 1_000_000:g}"}
    return out


# ------------------------------------------------------------------------------------------- main
def verify_pitch(draft: ExecutivePitchDraft, profile: BusinessProfile, llm=None, model: str | None = None,
                 effort: str = "low", system: str = "") -> tuple[ExecutivePitchDraft, VerificationReport]:
    d = draft.model_dump(mode="json")
    facts = list(profile.facts)
    by_id = {f.fact_id: f for f in facts}
    index = _number_index(facts)
    quotes = " ".join(p.quote for p in profile.stated_priorities)
    roi_vals = _roi_values(draft)
    current_last = {_last(e.split("—")[0]) for e in profile.leadership}
    claims: list[VerifiedClaim] = []
    report = VerificationReport()
    unresolved: set[str] = set()

    def add(kind, text, field, sentence, status=None, evidence=(), note=""):
        c = VerifiedClaim(id=f"C{len(claims) + 1}", kind=kind, text=text.strip(), field=field, sentence=sentence[:300],
                          status=status or "unsupported", evidence=list(evidence), note=note)
        if status is None:
            unresolved.add(c.id)
        claims.append(c)
        return c

    fields = _text_fields(d)

    # ---- 1. names
    known: dict[str, str] = {}
    for w in profile.provenance_warnings:
        m = re.match(r"Leader '([^']+)' \(([^)]*)\)", w)
        if m:
            known[m.group(1)] = m.group(2)
    for st in profile.leader_statements:
        known.setdefault(st.get("speaker", ""), st.get("role", ""))
    for leader in profile.leaders:
        known.setdefault(leader.name, leader.role)
    person = addressed_person(d.get("addressed_to", ""))
    if person:
        known.setdefault(person, d.get("recipient_role", ""))
    replacements: dict[str, str] = {}
    seen_last: set[str] = set()
    for name, role in sorted(known.items(), key=lambda kv: -len(kv[0])):
        if not name or not _last(name) or _last(name) in seen_last:
            continue
        hits = [(f, t) for _p, f, t in fields if name.lower() in t.lower()
                or (f == "addressed_to" and person and _last(person) == _last(name))]
        if not hits:
            continue
        seen_last.add(_last(name))
        ok = _last(name) in current_last
        ev = [e for leader in profile.leaders if _last(leader.name) == _last(name) for e in leader.evidence]
        c = add("name", name, hits[0][0], hits[0][1], "supported" if ok else "unsupported", ev,
                "" if ok else "not a current leader with evidence from the last 12 months")
        if not ok:
            c.action = "replaced"
            replacements[name] = role or d.get("recipient_role") or "Managing Director"

    # ---- 2. numbers and 3. periods
    for _path, field, text in fields:
        if field in ("addressed_to",):
            continue
        for m in NUMBER.finditer(text):
            vals = values(m.group(0))
            if not vals:
                continue
            sentence = _sentence_of(text, m.start())
            matched = [f for v in vals for f in index.get(v, [])]
            if matched:
                current = [f for f in matched if not f.superseded_by]
                if current:
                    add("number", m.group(0), field, sentence, "supported", sorted({f.fact_id for f in current}))
                else:
                    newer = sorted({f.superseded_by for f in matched if f.superseded_by})
                    newest = by_id.get(newer[0]) if newer else None
                    add("number", m.group(0), field, sentence, "stale", sorted({f.fact_id for f in matched}) + newer,
                        f"superseded by {', '.join(newer)}" + (f": {newest.statement[:120]}" if newest else ""))
            elif any(v in quotes for v in vals):
                add("number", m.group(0), field, sentence, "supported", [p.source_id for p in profile.stated_priorities])
            elif PROJECTION.search(sentence) or field.startswith("recommended_") or (
                    field not in FACTUAL_FIELDS and any(v in roi_vals for v in vals)):
                # An ROI input stated as fact in a factual paragraph is still a claim to check.
                add("number", m.group(0), field, sentence, "estimate", note="projection or ROI-model figure")
            else:
                add("number", m.group(0), field, sentence)
        for m in PERIOD.finditer(text):
            iso = parse_as_of(m.group(0))
            if not iso:
                continue
            gran = _granularity(m.group(0))
            same = [f for f in facts if f.period and parse_as_of(f.period) == iso]
            newer = [f for f in facts if f.period and not f.superseded_by and _granularity(f.period) == gran
                     and (parse_as_of(f.period) or "") > iso and f.metric
                     and any(g.metric == f.metric for g in same)]
            sentence = _sentence_of(text, m.start())
            if same and newer and all(f.superseded_by for f in same if f.metric == newer[0].metric):
                add("period", m.group(0), field, sentence, "stale", [newer[0].fact_id],
                    f"newer period available: {newer[0].period} ({newer[0].fact_id})")
            elif same:
                add("period", m.group(0), field, sentence, "supported", sorted({f.fact_id for f in same})[:4])
            else:
                add("period", m.group(0), field, sentence)

    # ---- one cheap-model call for what Python couldn't resolve
    leftovers = [c for c in claims if c.id in unresolved]
    if leftovers and llm is not None and model:
        batch = leftovers[:MAX_LLM_CLAIMS]
        current_facts = sorted((f for f in facts if not f.superseded_by), key=lambda f: f.as_of or "", reverse=True)
        evidence = "\n".join(f"{f.fact_id} [{f.as_of or 'undated'}] {f.statement}" for f in current_facts[:80])
        user = (f"<facts>\n{evidence}\n</facts>\n\n<claims>\n"
                + "\n".join(f'{c.id} [{c.kind}] "{c.text}" in: {c.sentence}' for c in batch)
                + "\n</claims>\n\nFor each claim: is it supported by the facts?")
        result = llm.structured(agent="verifier", system=system, user=user, schema=ClaimVerdicts, model=model,
                                effort=effort, max_tokens=2000)
        verdicts = {v.claim_id: v for v in result.verdicts}
        report.llm_checked = len(batch)
        for c in batch:
            v = verdicts.get(c.id)
            if not v:
                continue
            ids = [i for i in v.fact_ids if i in by_id]
            if v.verdict == "yes" and ids:
                c.status, c.evidence, c.note = "supported", ids, "confirmed by the cheap-model check"
            elif v.verdict in ("yes", "partial"):
                c.status, c.evidence, c.note = "partial", ids, "partly supported (cheap-model check)"

    # ---- actions
    for name, role in replacements.items():
        report.actions.append(f"Replaced '{name}' with '{role}' (no current evidence)")
    for path, _field, _text in fields:
        text = _get(d, path)
        if path == ("addressed_to",) and person and person in replacements:
            text = d.get("recipient_role") or replacements[person]
        for name, role in replacements.items():
            last = re.escape(_last(name).capitalize())
            text = re.sub(rf"\bDear\s+(?:{HONORIFIC})?(?:{re.escape(name)}|{last})\b", f"Dear {role}", text, flags=re.I)
            text = re.sub(rf"(?:{HONORIFIC})?{re.escape(name)}", f"the {role}", text, flags=re.I)
        _set(d, path, text)

    removed_sentences: set[tuple[str, str]] = set()
    for c in claims:
        if c.kind == "name":
            continue
        if c.status in ("stale", "partial"):
            c.action = "flagged"
        elif c.status == "unsupported":
            c.action = "removed" if c.field in FACTUAL_FIELDS else "flagged"
            if c.action == "removed":
                removed_sentences.add((c.field, c.sentence))
    for path, field, _t in fields:
        if field not in FACTUAL_FIELDS:
            continue
        text = _get(d, path)
        parts = [s for s in _SENTENCE.split(text) if (field, s.strip()) not in removed_sentences]
        if len(parts) < len(_SENTENCE.split(text)):
            if parts:
                _set(d, path, " ".join(p.strip() for p in parts))
            else:   # never blank a whole paragraph; keep it and downgrade to flagged
                for c in claims:
                    if c.field == field and c.action == "removed" and c.sentence in text:
                        c.action = "flagged"
    for c in claims:
        if c.action == "removed":
            report.actions.append(f"Removed unsupported figure '{c.text}' from {c.field}")
        elif c.action == "flagged":
            report.actions.append(f"Flagged {c.status} {c.kind} '{c.text}' in {c.field}" + (f" ({c.note})" if c.note else ""))

    factual = [c for c in claims if c.status != "estimate"]
    report.claims = claims
    report.checked = len(factual)
    report.supported = sum(c.status == "supported" for c in factual)
    report.estimates = len(claims) - len(factual)
    report.pass_rate = round(report.supported / report.checked, 3) if report.checked else None
    return ExecutivePitchDraft.model_validate(d), report
