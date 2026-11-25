"""Evals over saved runs (outputs/<slug>/). Nothing here runs the pipeline.

(a) cross-company similarity: how alike different companies' AI opportunities are (lower = more specific).
    Dependency-free TF-IDF cosine by default; Gemini embeddings only when asked for and a key is set.
(b) LLM judge: the cheap model scores each report on the assessment criteria a single report can show
    (reasoning 30, research 20, practicality 20, renormalized) plus specificity. Cached per report.
(c) verifier pass rate, from 04_verification.json.
(d) tokens, calls and time per run, from 00_run_meta.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from pydantic import BaseModel, Field

from agents.report import build_report
from utils.schemas import AssessmentReport, CriterionScore

JUDGE_FILE = "06_eval_judge.json"
JUDGE_WEIGHTS = {"reasoning": 0.30, "research": 0.20, "practicality": 0.20}   # from the assessment rubric
STOP = set("""a an and are as at be by for from has have in into is it its of on or that the their this to with
will can using based each per via our your they them than then over more most less such also which who what when""".split())


# ------------------------------------------------------------------------------------------- loading
@dataclass
class Run:
    slug: str
    path: Path
    report: AssessmentReport
    meta: dict = field(default_factory=dict)
    legacy: bool = False


def load_runs(outputs: Path, only: list[str] | None = None) -> tuple[list[Run], list[str]]:
    runs, skipped = [], []
    for d in sorted(p for p in outputs.iterdir() if p.is_dir()):
        if only and d.name not in only:
            continue
        try:
            report = build_report(d)
        except Exception as exc:  # noqa: BLE001 - a half-finished folder shouldn't stop the eval
            skipped.append(f"{d.name}: {exc.__class__.__name__}")
            continue
        if not report.ai_opportunities:
            skipped.append(f"{d.name}: no AI opportunities yet")
            continue
        meta_path = d / "00_run_meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        legacy = not meta.get("stages") or not (report.trace and report.citations)
        runs.append(Run(d.name, d, report, meta, legacy))
    return runs, skipped


# ------------------------------------------------------------------------------------------- (a) similarity
def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9]+", text.lower()) if w not in STOP and len(w) > 2]


def opportunity_texts(report: AssessmentReport) -> list[str]:
    return [f"{o.title}. {o.ai_mechanism}" for o in report.ai_opportunities]


def tfidf_vectors(docs: list[str]) -> list[dict[str, float]]:
    tokens = [Counter(_words(d)) for d in docs]
    df = Counter(w for t in tokens for w in t)
    n = len(docs)
    vecs = []
    for t in tokens:
        v = {w: (c / max(1, sum(t.values()))) * (math.log((1 + n) / (1 + df[w])) + 1) for w, c in t.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({w: x / norm for w, x in v.items()})
    return vecs


def cosine(a: dict[str, float] | list[float], b: dict[str, float] | list[float]) -> float:
    if isinstance(a, dict):
        return sum(x * b.get(w, 0.0) for w, x in a.items())
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def cross_company_similarity(texts: dict[str, list[str]], vectors=None) -> dict:
    """Mean cosine over every pair of opportunities from *different* companies, overall and per company."""
    slugs = [s for s in texts if texts[s]]
    flat = [(s, t) for s in slugs for t in texts[s]]
    vecs = vectors or tfidf_vectors([t for _, t in flat])
    owner = [s for s, _ in flat]
    per: dict[str, list[float]] = {s: [] for s in slugs}
    pairs = []
    for i, j in combinations(range(len(flat)), 2):
        if owner[i] == owner[j]:
            continue
        c = cosine(vecs[i], vecs[j])
        pairs.append(c)
        per[owner[i]].append(c)
        per[owner[j]].append(c)
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else None  # noqa: E731
    return {"overall": mean(pairs), "per_company": {s: mean(v) for s, v in per.items()}, "pairs": len(pairs)}


def gemini_embeddings(docs: list[str], api_key: str, model: str) -> list[list[float]]:
    from google import genai   # imported lazily: only used when --embeddings gemini

    client = genai.Client(api_key=api_key)
    resp = client.models.embed_content(model=model, contents=docs)
    return [list(e.values) for e in resp.embeddings]


# ------------------------------------------------------------------------------------------- (b) judge
class JudgeScores(BaseModel):
    reasoning: CriterionScore = Field(description="Problem solving and reasoning: are challenges and ideas argued from evidence?")
    research: CriterionScore = Field(description="Quality of research: specific, recent, sourced facts about this company")
    practicality: CriterionScore = Field(description="Practical recommendations: realistic pilots, vendors, data, compliance")
    specificity: CriterionScore = Field(description="Company-specific rather than generic advice (10 = could only be about this company)")
    biggest_weakness: str


def judge_input(report: AssessmentReport, limit: int = 12_000) -> str:
    """A compact view of the report: what a reviewer would read, without boilerplate."""
    r = report
    ov = r.company_overview
    lines = [f"# {r.business_name} ({ov.industry}; data quality {r.data_quality})", ov.what_they_do, "",
             "Leadership: " + (", ".join(ov.leadership) or "unknown"), "", "## Challenges"]
    for c in r.business_challenges:
        lines.append(f"- {c.title}: {c.reasoning[:400]} | signals: {'; '.join(c.signals)[:200]}")
    lines.append("\n## AI opportunities")
    for o in r.ai_opportunities:
        extra = []
        if o.build_vs_buy:
            extra.append(f"{o.build_vs_buy.decision}: {', '.join(o.build_vs_buy.vendors) or 'no vendor'}")
        if o.pilot_30_60_90:
            extra.append("pilot: " + "; ".join(f"d{m.day} {m.kpi} {m.target}" for m in o.pilot_30_60_90))
        if o.evidence_share is not None:
            extra.append(f"evidence share {o.evidence_share:.0%}")
        lines.append(f"- #{o.rank} {o.title} (score {o.weighted_score}): {o.ai_mechanism[:300]} "
                     f"| applies to {o.applies_to[:150]} | {' | '.join(extra)}")
    if r.ceo_pitch:
        p = r.ceo_pitch
        lines += ["\n## CEO pitch", f"To: {p.addressed_to}", p.opening.text if p.opening else "", p.why_we_reached_out,
                  *[f"- {o.title}: {o.evidence}" for o in p.opportunities_identified]]
    if r.verification and r.verification.pass_rate is not None:
        lines.append(f"\nVerifier: {r.verification.supported}/{r.verification.checked} claims supported.")
    lines.append(f"Sources cited: {len(r.citations) or len(r.sources)}")
    return "\n".join(lines)[:limit]


def judge_weighted(scores: JudgeScores) -> float:
    total = sum(JUDGE_WEIGHTS.values())
    return round(sum(getattr(scores, k).score * w for k, w in JUDGE_WEIGHTS.items()) / total * 10, 1)


def judge_run(run: Run, llm, model: str, system: str, refresh: bool = False) -> tuple[JudgeScores, bool]:
    """Returns (scores, from_cache). One cheap-model call per report, cached by the report's content."""
    text = judge_input(run.report)
    digest = hashlib.sha1(f"{model}\n{text}".encode()).hexdigest()
    cache = run.path / JUDGE_FILE
    if cache.exists() and not refresh:
        saved = json.loads(cache.read_text())
        if saved.get("digest") == digest:
            return JudgeScores.model_validate(saved["scores"]), True
    scores = llm.structured(agent="eval.judge", system=system, user=f"<report>\n{text}\n</report>\n\nScore this report.",
                            schema=JudgeScores, model=model, effort="low", max_tokens=1500)
    for k in ("reasoning", "research", "practicality", "specificity"):
        cs = getattr(scores, k)
        cs.score = max(1, min(10, int(cs.score)))
    cache.write_text(json.dumps({"digest": digest, "model": model, "scores": scores.model_dump()}, indent=2))
    return scores, False


# ------------------------------------------------------------------------------------------- (c), (d) and the table
def run_metrics(run: Run) -> dict:
    m, v = run.meta, run.report.verification
    stages = m.get("stages") or {}
    calls = sum(s.get("calls", 0) for s in stages.values()) if stages else None
    return {
        "pass_rate": v.pass_rate if v else None,
        "claims": f"{v.supported}/{v.checked}" if v and v.checked else None,
        "tokens_in": m.get("total_input_tokens"),
        "tokens_out": m.get("total_output_tokens"),
        "calls": calls,
        "seconds": m.get("elapsed_seconds"),
        "citations": len(run.report.citations),
        "uncited": len(run.report.trace.uncited) if run.report.trace else None,
    }


def _fmt(x, pct: bool = False) -> str:
    if x is None:
        return "—"
    if pct:
        return f"{x:.0%}"
    return f"{x:,}" if isinstance(x, int) else str(x)


def results_markdown(runs: list[Run], similarity: dict, sim_method: str, judged: dict[str, JudgeScores],
                     judge_model: str | None, skipped: list[str]) -> str:
    lines = [
        "| Company | Run | Similarity ↓ | Judge (0-100) | Reasoning | Research | Practicality | Specificity "
        "| Verified | Citations | Tokens in / out | Calls | Time |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in runs:
        m = run_metrics(r)
        j = judged.get(r.slug)
        js = [getattr(j, k).score if j else "—" for k in ("reasoning", "research", "practicality", "specificity")]
        tokens = (f"{_fmt(m['tokens_in'])} / {_fmt(m['tokens_out'])}" if m["tokens_in"] is not None else "—")
        verified = f"{_fmt(m['pass_rate'], pct=True)} ({m['claims']})" if m["claims"] else "—"
        lines.append(
            f"| {r.report.business_name} | {'legacy' if r.legacy else 'current'} | "
            f"{_fmt(similarity['per_company'].get(r.slug))} | {judge_weighted(j) if j else '—'} | "
            + " | ".join(str(x) for x in js)
            + f" | {verified} | {m['citations'] or '—'} | {tokens} | {_fmt(m['calls'])} | "
            f"{_fmt(round(m['seconds'])) + ' s' if m['seconds'] else '—'} |")
    notes = [
        "",
        f"- **Similarity** is the mean cosine between this company's AI opportunities and every other company's "
        f"({sim_method}); lower means more company-specific. Overall: **{_fmt(similarity['overall'])}** over "
        f"{similarity['pairs']} cross-company pairs.",
        "- **Judge** is " + (f"`{judge_model}`, one call per report, cached in `{JUDGE_FILE}`. " if judge_model else
                             "not run (pass `--judge`). ")
        + "It scores the criteria a single report can show: reasoning (30), research (20) and practicality (20), "
          "renormalized to 0-100; specificity is reported but not weighted. AI tool usage, product quality and "
          "documentation are project-level and aren't judged per report.",
        "- **Verified** is the Phase 3 verifier's pass rate over factual claims in the pitch (estimates excluded).",
        "- **legacy** runs were saved before the Phase 1-6 upgrade: no per-stage tokens, verifier or citations.",
    ]
    if skipped:
        notes.append("- Skipped: " + "; ".join(skipped))
    return "\n".join(lines + notes) + "\n"


def write_readme_section(readme: Path, table: str) -> bool:
    """Replace the block between the eval markers in the README (added once if missing)."""
    start, end = "<!-- eval:start -->", "<!-- eval:end -->"
    text = readme.read_text(encoding="utf-8")
    block = f"{start}\n{table}{end}"
    if start in text and end in text:
        new = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _m: block, text, flags=re.S)
    else:
        new = text.rstrip() + f"\n\n## Evaluation results\n\nGenerated by `python scripts/eval.py`.\n\n{block}\n"
    readme.write_text(new, encoding="utf-8")
    return new != text
