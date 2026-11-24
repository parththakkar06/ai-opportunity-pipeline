"""Agent 1: Business Intelligence Researcher -> 01_business_profile.json"""
from __future__ import annotations

from pathlib import Path

from agents.base import PROFILE_JSON, Agent
from utils.io import write_json
from utils.schemas import BusinessProfile
from utils.search import HomepageSignals, Query, ResearchBundle, domain_of, guess_official_website, normalize_url

MAX_EVIDENCE_CHARS = 30_000
THIN_RESULT_THRESHOLD = 6


def build_queries(name: str, url: str | None, context: str | None) -> list[Query]:
    anchor = f'"{name}"'
    if url:
        anchor = f'"{name}" {domain_of(url)}'
    elif context:
        anchor = f'"{name}" {context}'
    queries = [
        Query(anchor),
        Query(f"{anchor} products services pricing"),
        Query(f"{anchor} reviews complaints"),
        Query(f"{anchor} careers jobs hiring"),
        Query(f"{name} news", topic="news"),
    ]
    if url:
        # Search providers reject a bare "site:" query, so pair the operator with real search terms.
        queries.insert(1, Query(f"{name} about projects investors site:{domain_of(url)}"))
    return queries


def format_evidence(bundle: ResearchBundle, homepage: HomepageSignals | None) -> str:
    parts: list[str] = []
    if homepage:
        parts.append(
            "<homepage>\n"
            f"url: {homepage.url}\n"
            f"title: {homepage.title}\n"
            f"meta_description: {homepage.meta_description}\n"
            f"theme_color: {homepage.theme_color}\n"
            f"detected_technologies: {', '.join(homepage.tech_signals) or 'none detected'}\n"
            f"headings: {' | '.join(homepage.headings)}\n"
            f"text_excerpt: {homepage.text_excerpt}\n"
            "</homepage>"
        )
    for i, r in enumerate(bundle.results, 1):
        date = f"\ndate: {r.date}" if r.date else ""
        parts.append(
            f"<result index=\"{i}\" query=\"{r.query}\">\n"
            f"title: {r.title}\nurl: {r.url}{date}\nsnippet: {r.snippet}\n</result>"
        )
    text = "\n\n".join(parts)
    if len(text) > MAX_EVIDENCE_CHARS:
        text = text[:MAX_EVIDENCE_CHARS] + "\n[evidence truncated]"
    return text


class ResearcherAgent(Agent):
    stage = 1
    key = "researcher"
    title = "Business Intelligence Researcher"

    def run(self) -> list[Path]:
        ctx = self.ctx
        ctx.status("searching the web…")
        bundle = ctx.research.search_many(build_queries(ctx.business_name, ctx.url, ctx.context))
        ctx.search_providers_used = bundle.providers_used
        ctx.note(f"{len(bundle.results)} unique results via {', '.join(bundle.providers_used) or 'no provider'}")
        if bundle.errors and not bundle.results:
            ctx.note("All search providers failed: " + "; ".join(bundle.errors[:3]))
        elif bundle.errors:
            ctx.note(f"{len(bundle.errors)} search issue(s); last: {bundle.errors[-1]}")

        website = normalize_url(ctx.url) if ctx.url else guess_official_website(ctx.business_name, bundle.results)
        homepage = None
        if website:
            ctx.status(f"reading homepage {website}…")
            homepage = ctx.research.fetch_homepage(website)
            ctx.note(f"homepage: {'read' if homepage else 'unreachable'} ({website})")

        thin = len(bundle.results) < THIN_RESULT_THRESHOLD and homepage is None
        if thin:
            ctx.note("limited public information found; the profile will lean on labelled assumptions")

        user = (
            f"Business name: {ctx.business_name}\n"
            f"User-provided URL (ground truth if present): {ctx.url or 'none'}\n"
            f"User-provided context (ground truth if present): {ctx.context or 'none'}\n"
            f"Likely official website: {website or 'unknown'}\n"
            f"Evidence volume: {len(bundle.results)} search results, homepage {'available' if homepage else 'unavailable'}."
            + (" Evidence is THIN: set data_quality to 'low' and label inferences as assumptions." if thin else "")
            + f"\n\n<evidence>\n{format_evidence(bundle, homepage) or 'No evidence was found.'}\n</evidence>\n\n"
            "Produce the business profile."
        )

        def check(profile: BusinessProfile) -> str | None:
            if not profile.operational_bottlenecks:
                return "operational_bottlenecks is empty; list 3-6 (use 'inferred from industry norms' when needed)."
            if not profile.core_products_services:
                return "core_products_services is empty."
            if not profile.geographic_presence:
                return "geographic_presence is empty; list where the company operates (use headquarters if that is all you know)."
            return None

        ctx.status("structuring the business profile…")
        profile = ctx.llm.structured(
            agent=self.key, system=self.prompt("researcher.md"), user=user, schema=BusinessProfile,
            model=ctx.settings.model, effort=ctx.settings.effort, check=check,
        )

        # Deterministic fix-ups the model shouldn't be trusted with.
        if not profile.website and website:
            profile.website = website
        if thin:
            profile.data_quality = "low"
        known_urls = {r.url for r in bundle.results} | ({homepage.url} if homepage else set())
        profile.sources = [s for s in profile.sources if s in known_urls] or sorted(known_urls)[:10]

        return [write_json(ctx.path(PROFILE_JSON), profile)]
