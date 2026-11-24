"""Stage 1: Business Intelligence Researcher -> 01_business_profile.json

Deep research within a fixed budget:
  1. search (cached per query)
  2. rank results and read up to MAX_DOCS full pages/PDFs (cached per URL, time-boxed)
  3. the cheap model turns each document into dated facts with ids (batched, cached per URL)
  4. the main model writes the profile from the facts only, citing fact ids
  5. Python enforces provenance (newest wins, 12-month leadership rule, no unsupported figures)
  6. at most one gap-filling round (skipped when data quality is high or time is short)
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

from agents.base import PROFILE_JSON, Agent
from agents.provenance import (
    detect_gaps, document_facts, format_evidence, gap_queries, mark_superseded, snippet_sources, validate_profile,
)
from utils.cache import DiskCache
from utils.fetch import FetchedDoc
from utils.io import write_json
from utils.schemas import BusinessProfile, BusinessProfileDraft, DocFacts, Fact, FactBatch, SourceDoc
from utils.search import HomepageSignals, Query, SearchResult, domain_of, guess_official_website, normalize_url
from utils.sources import Candidate, rank_sources

THIN_RESULT_THRESHOLD = 6
EXTRACT_BATCH = 3
MIN_SECONDS_FOR_GAP_ROUND = 25


def build_queries(name: str, url: str | None, context: str | None, year: int | None = None) -> list[Query]:
    """Ordered by value: the first ones survive when keyless search caps the number of queries."""
    year = year or date.today().year
    anchor = f'"{name}"'
    if url:
        anchor = f'"{name}" {domain_of(url)}'
    elif context:
        anchor = f'"{name}" {context}'
    queries = [
        Query(anchor),
        Query(f'"{name}" managing director OR CEO {year}', topic="news"),
        Query(f'"{name}" investor presentation {year} pdf'),
        Query(f'"{name}" quarterly results operational update {year}'),
        Query(f"{name} news", topic="news"),
        Query(f'"{name}" earnings call transcript'),
        Query(f"{anchor} reviews complaints"),
        Query(f'"{name}" RERA registered new launch'),
    ]
    if url:
        # Search providers reject a bare "site:" query, so pair the operator with real search terms.
        queries.insert(1, Query(f"{name} investor relations results site:{domain_of(url)}"))
    return queries


def homepage_block(homepage: HomepageSignals | None) -> str:
    if not homepage:
        return ""
    return (
        "## Homepage signals (live, retrieved today)\n"
        f"url: {homepage.url} · title: {homepage.title} · theme_color: {homepage.theme_color}\n"
        f"meta_description: {homepage.meta_description}\n"
        f"detected_technologies: {', '.join(homepage.tech_signals) or 'none detected'}\n"
        f"headings: {' | '.join(homepage.headings[:15])}\n"
        f"text_excerpt: {homepage.text_excerpt[:1500]}"
    )


class ResearcherAgent(Agent):
    stage = 1
    key = "researcher"
    title = "Business Intelligence Researcher"

    def run(self) -> list[Path]:
        ctx, settings = self.ctx, self.ctx.settings
        started = time.monotonic()
        remaining = lambda: settings.research_time_budget_s - (time.monotonic() - started)  # noqa: E731
        cache = DiskCache(ctx.out_dir / "cache", enabled=not settings.refresh_cache)
        stats = ctx.research_stats
        stats.update(pages_fetched=0, pages_failed=0, documents=0, facts=0, gap_round=False, cache_hits=0)

        # 1. search
        ctx.status("searching the web…")
        bundle = ctx.research.search_many(build_queries(ctx.business_name, ctx.url, ctx.context), cache=cache)
        ctx.search_providers_used = bundle.providers_used
        ctx.note(f"{len(bundle.results)} unique results via {', '.join(bundle.providers_used) or 'no provider'}")
        if bundle.errors and not bundle.results:
            ctx.note("All search providers failed: " + "; ".join(bundle.errors[:3]))
        elif bundle.errors:
            ctx.note(f"{len(bundle.errors)} search issue(s); last: {bundle.errors[-1]}")

        website = normalize_url(ctx.url) if ctx.url else guess_official_website(ctx.business_name, bundle.results)
        domain = domain_of(website) if website else None
        homepage = None
        if website:
            ctx.status(f"reading homepage {website}…")
            homepage = ctx.research.fetch_homepage(website)
            ctx.note(f"homepage: {'read' if homepage else 'unreachable'} ({website})")

        # 2–3. read the best sources in full and extract dated facts
        sources: list[SourceDoc] = []
        facts: list[Fact] = []
        statements: list[dict] = []
        chosen = rank_sources(bundle.results, domain, limit=settings.max_docs)
        self._read_and_extract(chosen, sources, facts, statements, cache, remaining)

        fetched_urls = {s.url for s in sources}
        snippet_src, snippet_facts = snippet_sources([r for r in bundle.results if r.url not in fetched_urls])
        sources += snippet_src
        facts = mark_superseded(facts + snippet_facts)

        thin = len(bundle.results) < THIN_RESULT_THRESHOLD and homepage is None and not stats["documents"]
        if thin:
            ctx.note("limited public information found; the profile will lean on labelled assumptions")

        # 4–5. profile from facts only, then provenance rules
        profile = self._write_profile(sources, facts, homepage, website, thin)
        profile.leader_statements = statements

        # 6. one gap-filling round
        if settings.gap_round and profile.data_quality != "high" and remaining() > MIN_SECONDS_FOR_GAP_ROUND:
            gaps = detect_gaps(profile)
            slots = settings.max_docs - stats["documents"]
            if gaps and slots > 0:
                stats["gap_round"] = True
                ctx.status(f"filling gaps: {', '.join(gaps)}…")
                ctx.note(f"gap round for: {', '.join(gaps)}")
                extra = ctx.research.search_many(gap_queries(ctx.business_name, gaps), cache=cache)
                new_results = [r for r in extra.results if r.url not in {s.url for s in sources}]
                picked = rank_sources(new_results, domain, limit=min(2, slots), exclude=fetched_urls)
                before = len(facts)
                self._read_and_extract(picked, sources, facts, statements, cache, remaining)
                new_src, new_snips = snippet_sources([r for r in new_results if r.url not in {s.url for s in sources}],
                                                     start=len([s for s in sources if s.kind == "snippet"]) + 1)
                sources += new_src
                facts = mark_superseded(facts + new_snips)
                if len(facts) > before:
                    profile = self._write_profile(sources, facts, homepage, website, thin, previous=profile)
                    profile.leader_statements = statements
                else:
                    ctx.note("gap round found nothing new")
        elif profile.data_quality == "high":
            ctx.note("data quality high; gap round skipped")

        stats["facts"] = len(facts)
        stats["cache_hits"] = cache.hits
        stats["seconds"] = round(time.monotonic() - started, 1)
        for w in profile.provenance_warnings[:4]:
            ctx.note(f"provenance: {w}")
        ctx.note(f"{stats['documents']} documents read, {len(facts)} facts, leadership: "
                 f"{'; '.join(profile.leadership) or 'unknown'}")
        return [write_json(ctx.path(PROFILE_JSON), profile)]

    # ----------------------------------------------------------------------------------------- helpers
    def _read_and_extract(self, chosen: list[Candidate], sources: list[SourceDoc], facts: list[Fact],
                          statements: list[dict], cache: DiskCache, remaining) -> None:
        ctx = self.ctx
        stats = ctx.research_stats
        docs: list[tuple[SourceDoc, FetchedDoc]] = []
        for c in chosen:
            if remaining() <= 5:
                ctx.note("research time budget reached; continuing with documents already read")
                break
            ctx.status(f"reading {c.result.url[:80]}…")
            cached = cache.get("pages", c.result.url)
            doc = FetchedDoc.from_dict(cached) if cached else ctx.research.fetch_document(c.result.url)
            if not cached and doc.ok:
                cache.set("pages", c.result.url, doc.to_dict())
            if not doc.ok:
                stats["pages_failed"] += 1
                ctx.note(f"couldn't read {c.result.url[:70]} ({doc.error})")
                continue
            stats["pages_fetched"] += 0 if cached else 1
            sid = f"S{len([s for s in sources if s.kind != 'snippet']) + len(docs) + 1}"
            source = SourceDoc(source_id=sid, url=c.result.url, title=(doc.title or c.result.title)[:200],
                               source_type=c.source_type, kind=doc.kind, published=doc.published or c.published,
                               retrieved=doc.retrieved)
            docs.append((source, doc))
        if not docs:
            return

        extracted: dict[str, DocFacts] = {}
        todo = []
        for source, doc in docs:
            hit = cache.get("facts", doc.url)
            if hit:
                extracted[source.source_id] = DocFacts.model_validate(hit)
            else:
                todo.append((source, doc))
        for i in range(0, len(todo), EXTRACT_BATCH):
            batch = todo[i:i + EXTRACT_BATCH]
            ctx.status(f"extracting facts from {len(batch)} document(s) with {ctx.settings.cheap_model}…")
            user = "\n\n".join(
                f'<document source_id="{s.source_id}" type="{s.source_type}" date_hint="{s.published or "unknown"}" '
                f'url="{s.url}">\nTitle: {s.title}\n{d.text}\n</document>' for s, d in batch
            ) + f"\n\nExtract facts about {ctx.business_name} from each document."
            result = ctx.llm.structured(agent=f"{self.key}.extract", system=self.prompt("fact_extractor.md"), user=user,
                                        schema=FactBatch, model=ctx.settings.cheap_model, effort="low",
                                        max_tokens=12000)
            returned = {d.source_id: d for d in result.documents}
            for pos, (source, doc) in enumerate(batch):
                # Match by source_id; fall back to position if the model renumbered.
                df = returned.get(source.source_id) or (result.documents[pos] if pos < len(result.documents) else None)
                if df is None:   # nothing usable from this document; cache that so reruns don't pay again
                    df = DocFacts(source_id=source.source_id, facts=[])
                extracted[source.source_id] = df
                cache.set("facts", doc.url, df.model_dump(mode="json"))

        for source, _doc in docs:
            df = extracted.get(source.source_id)
            sources.append(source)
            stats["documents"] += 1
            if not df:
                continue
            facts.extend(document_facts(df, source))
            for st in df.leader_statements:
                statements.append({**st.model_dump(), "source_id": source.source_id})

    def _write_profile(self, sources: list[SourceDoc], facts: list[Fact], homepage: HomepageSignals | None,
                       website: str | None, thin: bool, previous: BusinessProfile | None = None) -> BusinessProfile:
        ctx = self.ctx
        evidence = format_evidence(sources, facts, homepage_block(homepage))
        docs_read = len([s for s in sources if s.kind != "snippet"])
        head = (
            f"Business name: {ctx.business_name}\n"
            f"User-provided URL (ground truth if present): {ctx.url or 'none'}\n"
            f"User-provided context (ground truth if present): {ctx.context or 'none'}\n"
            f"Likely official website: {website or 'unknown'}\n"
            f"Today: {date.today().isoformat()}\n"
            f"Evidence: {docs_read} full documents, {len(facts)} facts, homepage "
            f"{'available' if homepage else 'unavailable'}."
            + (" Evidence is THIN: set data_quality to 'low' and label inferences as assumptions." if thin else "")
        )
        if previous is None:
            user = f"{head}\n\n<evidence>\n{evidence or 'No evidence was found.'}\n</evidence>\n\nProduce the business profile."
        else:
            prior = previous.model_dump(mode="json", exclude={"facts", "sources_index", "leader_statements",
                                                              "provenance_warnings", "sources", "leadership"})
            user = (f"{head}\n\nA gap-filling round added evidence. Update the profile: keep what is still supported, "
                    f"replace anything a newer fact contradicts, fill gaps, and cite fact ids.\n\n"
                    f"<previous_profile>\n{prior}\n</previous_profile>\n\n<evidence>\n{evidence}\n</evidence>")

        def check(draft: BusinessProfileDraft) -> str | None:
            if not draft.operational_bottlenecks:
                return "operational_bottlenecks is empty; list 3-6 (use 'inferred from industry norms' when needed)."
            if not draft.core_products_services:
                return "core_products_services is empty."
            if not draft.geographic_presence:
                return "geographic_presence is empty; list where the company operates (use headquarters if that is all you know)."
            if facts and not draft.field_evidence:
                return "field_evidence is empty; cite the fact ids that support each factual field."
            return None

        ctx.status("updating the profile with new evidence…" if previous else "structuring the business profile…")
        draft = ctx.llm.structured(agent=self.key, system=self.prompt("researcher.md"), user=user,
                                   schema=BusinessProfileDraft, model=ctx.settings.model, effort=ctx.settings.effort,
                                   check=check)
        if not draft.website and website:
            draft.website = website
        if thin:
            draft.data_quality = "low"
        return validate_profile(draft, sources, facts)
