"""Traceability, in plain Python (no LLM): fact -> challenge -> opportunity -> pitch line.

Links come from evidence the run already holds, strongest first:
1. fact ids written in the text (the analyst cites ids like S2.F3 in challenge signals);
2. the verifier's evidence for claims in a pitch sentence (Phase 3);
3. the opening's source id and the value drivers' cited facts (Phases 2 and 4);
4. otherwise, the current facts sharing the most content words (and figures) with the text, at least 2.
Sources get report-wide numbers [n] in order of first use, pitch first, so the pitch reads [1], [2], ...
A factual pitch line with no resolvable source is listed in `trace.uncited` and shown as such.
"""
from __future__ import annotations

import re

from agents.verifier import values
from utils.schemas import (
    AIOpportunities, AssessmentReport, BusinessChallenge, BusinessProfile, Citation, Fact, KeyMetric, Trace,
    TraceEdge, TraceNode, WinningStrategy,
)

FACT_ID = re.compile(r"\b(S\d+\.F\d+|R\d+)\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
MIN_OVERLAP = 2
STOP = set("""about above after again also among because been before being below between both could does doing during
each even every from further have having here into just like made make many more most much must need only other over
same should since some such than that their them then there these they this those through under until upon very want
were what when where which while will with within without would your yours year years month months week weeks""".split())


def _tokens(text: str, ignore: set[str]) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w.isdigit():
            continue                      # figures are matched separately, by value
        if len(w) < 4 or w in STOP or w in ignore:
            continue
        out.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return out


class _Matcher:
    def __init__(self, facts: list[Fact], business_name: str):
        self.ignore = _tokens(business_name, set()) | {"company", "business", "limited", "group"}
        self.facts = [f for f in facts if not f.superseded_by]
        self.by_id = {f.fact_id: f for f in facts}
        self.index = [(f, _tokens(f"{f.statement} {f.value or ''}", self.ignore), set(values(f"₹ {f.statement}")))
                      for f in self.facts]

    def explicit(self, text: str) -> list[str]:
        return [i for i in dict.fromkeys(FACT_ID.findall(text)) if i in self.by_id]

    def overlap(self, text: str, limit: int = 2) -> list[str]:
        words, nums = _tokens(text, self.ignore), set(values(text))
        scored = []
        for f, fw, fn in self.index:
            score = len(words & fw) + 2 * len(nums & fn)
            if score >= MIN_OVERLAP:
                scored.append((score, f.fact_id.startswith("S"), f.as_of or "", f.fact_id))
        scored.sort(reverse=True)
        return [s[-1] for s in scored[:limit]]

    def find(self, text: str, limit: int = 2) -> list[str]:
        return self.explicit(text) or self.overlap(text, limit)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text or "") if s.strip()]


def build_trace(report: AssessmentReport, profile: BusinessProfile, challenges: list[BusinessChallenge],
                opps: AIOpportunities | None, strategy: WinningStrategy | None) -> tuple[list[Citation], Trace]:
    m = _Matcher(profile.facts, profile.business_name)
    sources = {s.source_id: s for s in profile.sources_index}
    nodes: dict[str, TraceNode] = {}
    edges: list[TraceEdge] = []

    def edge(a: str, b: str) -> None:
        if a in nodes and b in nodes and TraceEdge(source=a, target=b) not in edges:
            edges.append(TraceEdge(source=a, target=b))

    def fact_node(fid: str) -> None:
        f = m.by_id.get(fid)
        if f and fid not in nodes:
            nodes[fid] = TraceNode(id=fid, kind="fact", label=f.statement[:200], facts=[fid])

    # ---- challenges
    for c in challenges:
        fids = list(dict.fromkeys(i for sig in c.signals for i in m.find(sig, limit=1)))
        nodes[c.id] = TraceNode(id=c.id, kind="challenge", label=c.title, facts=fids)
        for fid in fids:
            fact_node(fid)
            edge(fid, c.id)

    # ---- opportunities
    drivers = {}
    if strategy:
        drivers = {r.opportunity_id: [i for d in r.scores.value_drivers for i in d.evidence if i in m.by_id]
                   for r in strategy.ranking}
    titles: dict[str, str] = {}
    for o in (opps.opportunities if opps else []):
        titles[o.id] = o.title
        own = drivers.get(o.id, []) + m.explicit(o.why_this_business)
        nodes[o.id] = TraceNode(id=o.id, kind="opportunity", label=o.title, facts=list(dict.fromkeys(own)))
        for fid in own:
            fact_node(fid)
            edge(fid, o.id)
        for cid in o.addresses_challenges:
            edge(cid, o.id)

    def best_opportunity(text: str) -> str | None:
        words = _tokens(text, m.ignore)
        scored = sorted(((len(words & _tokens(t, m.ignore)), oid) for oid, t in titles.items()), reverse=True)
        return scored[0][1] if scored and scored[0][0] >= 1 else None

    # ---- pitch lines
    pitch_ids: list[str] = []
    factual: list[str] = []
    p = report.ceo_pitch
    claims = report.verification.claims if report.verification else []

    def pitch_node(nid: str, field: str, text: str, extra: list[str], is_factual: bool) -> TraceNode:
        from_claims = [i for c in claims if c.field == field and c.sentence and c.sentence in text
                       and c.status in ("supported", "stale", "partial") for i in c.evidence if i in m.by_id]
        fids = list(dict.fromkeys(extra + from_claims + m.find(text)))
        node = TraceNode(id=nid, kind="pitch", label=text, field=field, facts=fids)
        nodes[nid] = node
        pitch_ids.append(nid)
        if is_factual:
            factual.append(nid)
        for fid in fids:
            fact_node(fid)
            edge(fid, nid)
        return node

    if p:
        if p.opening:
            sid = p.opening.source_id
            extra = [sid] if sid in m.by_id else [f.fact_id for f in profile.facts if f.source_id == sid][:1]
            node = pitch_node("pitch-opening", "opening", p.opening.text, extra, True)
            if sid in sources and not node.facts:
                node.facts = []          # a quote cites its source document directly (handled below)
        for i, s in enumerate(_sentences(p.why_we_reached_out), 1):
            pitch_node(f"pitch-why-{i}", "why_we_reached_out", s, [], True)
        for i, o in enumerate(p.opportunities_identified, 1):
            n = pitch_node(f"pitch-opp-{i}", "opportunities_identified.evidence", f"{o.title}: {o.evidence}", [], True)
            oid = best_opportunity(o.title)
            if oid:
                edge(oid, n.id)
        for i, s in enumerate(p.recommended_solutions, 1):
            oid = best_opportunity(f"{s.name} {s.what_it_does}")
            inherited = nodes[oid].facts if oid else []
            n = pitch_node(f"pitch-sol-{i}", "recommended_solutions", f"{s.name}: {s.what_it_does}", list(inherited), False)
            if oid:
                edge(oid, n.id)

    # ---- a pitch line resting on the same facts as a challenge or idea joins that chain
    upstream = [n for n in nodes.values() if n.kind in ("challenge", "opportunity") and n.facts]
    for nid in pitch_ids:
        shared = set(nodes[nid].facts)
        for u in upstream:
            if shared & set(u.facts):
                edge(u.id, nid)

    # ---- citations: number sources by first use (pitch, then challenges, then opportunities)
    order = pitch_ids + [c.id for c in challenges] + list(titles)
    numbers: dict[str, int] = {}
    citations: list[Citation] = []

    def cite(source_id: str) -> int | None:
        src = sources.get(source_id)
        if not src:
            return None
        if source_id not in numbers:
            numbers[source_id] = len(citations) + 1
            citations.append(Citation(n=numbers[source_id], source_id=source_id, url=src.url, title=src.title,
                                      date=src.published or src.retrieved, source_type=src.source_type))
        return numbers[source_id]

    for nid in order:
        node = nodes.get(nid)
        if not node:
            continue
        srcs = [m.by_id[f].source_id for f in node.facts if f in m.by_id]
        if nid == "pitch-opening" and p and p.opening and p.opening.source_id in sources:
            srcs.insert(0, p.opening.source_id)
        node.citations = [n for n in dict.fromkeys(cite(s) for s in srcs) if n is not None]
    for node in nodes.values():
        if node.kind == "fact":
            n = cite(m.by_id[node.id].source_id)
            node.citations = [n] if n else []

    metrics = _key_metrics(profile, m, cite)

    uncited = [nid for nid in factual if not nodes[nid].citations]
    ordered = [nodes[i] for i in order if i in nodes] + [n for n in nodes.values() if n.kind == "fact"]
    return citations, Trace(nodes=ordered, edges=edges, uncited=uncited), metrics


_FIGURE = re.compile(r"[~≈]?\s*(?:[$₹€£]|Rs\.?\s?|INR\s?|USD\s?)?\d[\d,.]*\s*(?:%|crore|cr\b|lakh|mn\b|million|bn\b|"
                     r"billion|[MBK]\b|sq\.?\s?ft|acres)?\+?", re.I)
_PERIOD = re.compile(r"\b(?:[QH][1-4]\s*)?FY\s*'?\d{2,4}(?:\s*[-–/]\s*\d{2,4})?\b|\b20\d{2}\b", re.I)
MAX_METRIC_CHARS = 22


def _compact_metric(label: str, value: str) -> tuple[str, str]:
    """'FY25 revenue ~$9M (estimated)' -> ('Revenue, FY25', '~$9M'). Short values are kept as written."""
    if len(value) <= MAX_METRIC_CHARS:
        return label, value
    period = _PERIOD.search(value)
    stripped = _PERIOD.sub(" ", value)
    figure = next((m.group(0).strip() for m in _FIGURE.finditer(stripped) if re.search(r"\d", m.group(0))), None)
    if not figure:
        return label, ""                       # prose isn't a headline figure; the caller leaves it out
    estimated = " (est.)" if re.search(r"estimat|approx|~|≈", value, re.I) and not figure.startswith(("~", "≈")) else ""
    return (f"{label}, {period.group(0)}" if period else label), figure + estimated


METRIC_LABELS = {"scale.revenue": "Revenue", "scale.projects_or_portfolio": "Portfolio", "scale.employees": "Employees"}
MAX_METRICS = 5


def _key_metrics(profile: BusinessProfile, m: _Matcher, cite) -> list[KeyMetric]:
    """Headline figures for the metrics strip, each backed by current, dated facts (else left out)."""
    evidence = {fe.field: fe.evidence for fe in profile.field_evidence}
    candidates: list[tuple[str, str, str]] = []
    for field, label in METRIC_LABELS.items():
        value = getattr(profile.scale, field.split(".")[1])
        if value:
            candidates.append((field, label, value))
    for i, value in enumerate(profile.scale.other_metrics):
        candidates.append((f"scale.other_metrics[{i}]", "", value))
    for leader in profile.leaders[:1]:
        candidates.append(("leaders[0]", leader.role, leader.name))

    out: list[KeyMetric] = []
    for field, label, value in candidates:
        ids = evidence.get(field) or (profile.leaders[0].evidence if field == "leaders[0]" else []) or m.find(value, 1)
        facts = [m.by_id[i] for i in ids if i in m.by_id and not m.by_id[i].superseded_by and m.by_id[i].as_of]
        if not facts:
            continue
        if not label:   # "~6,500 active patients" -> label "Active patients", value "~6,500"
            match = re.match(r"^\s*([~≈<>]?\s*[$₹€£]?[\d.,]+\s*(?:%|crore|cr|lakh|mn|million|bn|billion|k)?\+?)\s*(.+)$",
                             value, re.I)
            label, value = (match.group(2).strip().capitalize(), match.group(1).strip()) if match else ("Metric", value)
        if field != "leaders[0]":
            label, value = _compact_metric(label, value)
            if not value:
                continue
        newest = max(f.as_of for f in facts)
        nums = [n for n in dict.fromkeys(cite(f.source_id) for f in facts) if n is not None]
        out.append(KeyMetric(label=label, value=value, date=newest, facts=[f.fact_id for f in facts], citations=nums))
        if len(out) == MAX_METRICS:
            break
    return out
