"""Web research: search with a Tavily -> Serper -> DuckDuckGo fallback chain, plus a homepage scrape."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Literal, Protocol
from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.config import Settings

Topic = Literal["general", "news"]
USER_AGENT = "Mozilla/5.0 (compatible; AIOpportunityPipeline/1.0)"

# DuckDuckGo fallback limits: keep a keyless run from stalling on throttling.
DDG_TIMEOUT_S = 8               # per HTTP request
DDG_MAX_QUERIES = 4             # fewer queries when DuckDuckGo is the only provider
PROVIDER_FAILURE_LIMIT = 2      # consecutive failures before a provider is skipped for this run
SEARCH_TIME_BUDGET_S = 75       # stop issuing new queries after this long
HOMEPAGE_TIMEOUT_S = 10


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str
    query: str
    date: str | None = None


@dataclass
class Query:
    text: str
    topic: Topic = "general"


@dataclass
class HomepageSignals:
    url: str
    title: str | None = None
    meta_description: str | None = None
    theme_color: str | None = None
    headings: list[str] = field(default_factory=list)
    text_excerpt: str = ""
    tech_signals: list[str] = field(default_factory=list)


@dataclass
class ResearchBundle:
    results: list[SearchResult] = field(default_factory=list)
    providers_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int, topic: Topic) -> list[SearchResult]: ...


# --------------------------------------------------------------------------- providers
class TavilySearch:
    name = "tavily"

    def __init__(self, api_key: str):
        from tavily import TavilyClient

        self.client = TavilyClient(api_key=api_key)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=8), reraise=True)
    def search(self, query: str, max_results: int, topic: Topic) -> list[SearchResult]:
        data = self.client.search(query=query, max_results=max_results, search_depth="advanced", topic=topic)
        return [
            SearchResult(title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("content", ""),
                         provider=self.name, query=query, date=r.get("published_date"))
            for r in data.get("results", [])
        ]


class SerperSearch:
    name = "serper"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=8), reraise=True)
    def search(self, query: str, max_results: int, topic: Topic) -> list[SearchResult]:
        endpoint = "news" if topic == "news" else "search"
        resp = httpx.post(
            f"https://google.serper.dev/{endpoint}",
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("news" if topic == "news" else "organic", [])[:max_results]
        return [
            SearchResult(title=i.get("title", ""), url=i.get("link", ""), snippet=i.get("snippet", ""),
                         provider=self.name, query=query, date=i.get("date"))
            for i in items
        ]


class DuckDuckGoSearch:
    """Keyless fallback. Tight per-request timeout, one quick retry, no long backoff."""

    name = "duckduckgo"

    def __init__(self, timeout: int = DDG_TIMEOUT_S):
        self.timeout = timeout

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=3), reraise=True)
    def search(self, query: str, max_results: int, topic: Topic) -> list[SearchResult]:
        from ddgs import DDGS

        ddgs = DDGS(timeout=self.timeout)
        if topic == "news":
            items = ddgs.news(query, max_results=max_results) or []
            return [
                SearchResult(title=i.get("title", ""), url=i.get("url", ""), snippet=i.get("body", ""),
                             provider=self.name, query=query, date=i.get("date"))
                for i in items
            ]
        items = ddgs.text(query, max_results=max_results) or []
        return [
            SearchResult(title=i.get("title", ""), url=i.get("href", ""), snippet=i.get("body", ""),
                         provider=self.name, query=query)
            for i in items
        ]


# --------------------------------------------------------------------------- homepage
TECH_PATTERNS: dict[str, str] = {
    "Shopify": r"cdn\.shopify\.com|myshopify",
    "WordPress": r"wp-content|wp-includes",
    "WooCommerce": r"woocommerce",
    "Wix": r"wixstatic|wix\.com",
    "Squarespace": r"squarespace",
    "Webflow": r"webflow",
    "Next.js": r"/_next/",
    "React": r"react-dom|data-reactroot",
    "Vue": r"vue(\.min)?\.js|data-v-",
    "HubSpot": r"hs-scripts|hubspot",
    "Salesforce/Pardot": r"pardot|salesforce",
    "Google Analytics / GTM": r"googletagmanager|google-analytics",
    "Meta Pixel": r"connect\.facebook\.net",
    "Hotjar": r"hotjar",
    "Segment": r"cdn\.segment\.com",
    "Intercom": r"intercom",
    "Zendesk": r"zdassets|zendesk",
    "Drift": r"drift\.com|driftt",
    "Tidio": r"tidio",
    "Stripe": r"js\.stripe\.com",
    "Klaviyo": r"klaviyo",
    "Mailchimp": r"mailchimp|list-manage",
    "Calendly": r"calendly",
    "OpenTable": r"opentable",
    "Toast": r"toasttab",
    "Square": r"squareup",
    "Cloudflare": r"cloudflare",
}


def normalize_url(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def domain_of(url: str) -> str:
    netloc = urlparse(normalize_url(url)).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def parse_homepage(url: str, html: str) -> HomepageSignals:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    lowered = html.lower()
    tech = [name for name, pattern in TECH_PATTERNS.items() if re.search(pattern, lowered)]

    def meta(name: str) -> str | None:
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        return tag.get("content").strip() if tag and tag.get("content") else None

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    headings = [h for h in headings if h][:25]
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    return HomepageSignals(
        url=url,
        title=soup.title.get_text(strip=True) if soup.title else None,
        meta_description=meta("description") or meta("og:description"),
        theme_color=meta("theme-color"),
        headings=headings,
        text_excerpt=text[:4000],
        tech_signals=tech,
    )


# --------------------------------------------------------------------------- facade
class WebResearch:
    """What Agent 1 uses. Tests swap in a fake with the same two methods."""

    def __init__(self, providers: list[SearchProvider], results_per_query: int = 5,
                 max_queries: int | None = None, time_budget_s: float = SEARCH_TIME_BUDGET_S):
        if not providers:
            raise ValueError("At least one search provider is required")
        self.providers = providers
        self.results_per_query = results_per_query
        self.max_queries = max_queries
        self.time_budget_s = time_budget_s
        self.tavily_client = None      # set when a Tavily key exists; used as a fetch fallback

    @classmethod
    def from_settings(cls, settings: Settings) -> "WebResearch":
        providers: list[SearchProvider] = []
        if settings.tavily_api_key:
            providers.append(TavilySearch(settings.tavily_api_key))
        if settings.serper_api_key:
            providers.append(SerperSearch(settings.serper_api_key))
        providers.append(DuckDuckGoSearch())
        keyless = len(providers) == 1
        research = cls(providers, settings.search_results_per_query,
                       max_queries=DDG_MAX_QUERIES if keyless else None)
        if settings.tavily_api_key:
            research.tavily_client = providers[0].client
        return research

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self.providers]

    def search_many(self, queries: list[Query], cache=None) -> ResearchBundle:
        """Run queries through the provider chain. With a DiskCache, repeated queries cost nothing."""
        bundle = ResearchBundle()
        seen: set[str] = set()
        failures: dict[str, int] = {}
        disabled: set[str] = set()
        started = time.monotonic()
        if self.max_queries is not None and len(queries) > self.max_queries:
            queries = queries[: self.max_queries]
        for q in queries:
            if time.monotonic() - started > self.time_budget_s:
                bundle.errors.append(f"search time budget ({self.time_budget_s:.0f}s) reached; "
                                     "continuing with the results gathered so far")
                break
            cache_key = f"{q.topic}|{q.text}"
            cached = cache.get("search", cache_key) if cache is not None else None
            if cached is not None:
                for item in cached.get("results", []):
                    r = SearchResult(**item)
                    key = r.url.rstrip("/").lower()
                    if r.url and key not in seen:
                        seen.add(key)
                        bundle.results.append(r)
                if cached.get("provider") and cached["provider"] not in bundle.providers_used:
                    bundle.providers_used.append(cached["provider"])
                continue
            for provider in self.providers:
                if provider.name in disabled:
                    continue
                try:
                    results = provider.search(q.text, self.results_per_query, q.topic)
                except Exception as exc:  # noqa: BLE001 - any provider failure means "try the next one"
                    failures[provider.name] = failures.get(provider.name, 0) + 1
                    bundle.errors.append(f"{provider.name} failed on {q.text!r}: {_short_error(exc)}")
                    if failures[provider.name] >= PROVIDER_FAILURE_LIMIT:
                        disabled.add(provider.name)
                        bundle.errors.append(f"{provider.name} skipped for the rest of this run after "
                                             f"{PROVIDER_FAILURE_LIMIT} consecutive failures")
                    continue
                failures[provider.name] = 0
                if not results:
                    continue
                if provider.name not in bundle.providers_used:
                    bundle.providers_used.append(provider.name)
                if cache is not None:
                    cache.set("search", cache_key, {"provider": provider.name,
                                                    "results": [r.__dict__ for r in results]})
                for r in results:
                    key = r.url.rstrip("/").lower()
                    if r.url and key not in seen:
                        seen.add(key)
                        bundle.results.append(r)
                break
        return bundle

    def fetch_document(self, url: str, timeout: float = 12.0):
        """Full text of a page or PDF (utils.fetch). Tests override this with fixtures."""
        from utils.fetch import fetch_document

        return fetch_document(url, timeout=timeout, tavily_client=self.tavily_client)

    def fetch_homepage(self, url: str) -> HomepageSignals | None:
        url = normalize_url(url)
        try:
            resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True,
                             timeout=HOMEPAGE_TIMEOUT_S)
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        if "html" not in resp.headers.get("content-type", "html"):
            return None
        return parse_homepage(str(resp.url), resp.text)


def _short_error(exc: Exception) -> str:
    """One clean line instead of a multi-line library traceback message."""
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    text = f"{type(exc).__name__}: {text}" if text else type(exc).__name__
    return text[:160]


DIRECTORY_DOMAINS = (
    "yelp.", "facebook.", "instagram.", "linkedin.", "wikipedia.", "twitter.", "x.com", "tiktok.",
    "youtube.", "google.", "bbb.org", "tripadvisor.", "glassdoor.", "indeed.", "crunchbase.",
    "yellowpages.", "mapquest.", "reddit.", "bloomberg.", "zoominfo.", "apple.com/maps",
)


def guess_official_website(business_name: str, results: list[SearchResult]) -> str | None:
    """Pick the first result whose domain looks like the business's own site."""
    tokens = [t for t in re.split(r"[^a-z0-9]+", business_name.lower()) if len(t) > 2]
    squashed = "".join(re.split(r"[^a-z0-9]+", business_name.lower()))
    for r in results:
        d = domain_of(r.url) if r.url else ""
        if not d or any(x in d for x in DIRECTORY_DOMAINS):
            continue
        label = d.split(".")[0]
        if squashed and (squashed in label.replace("-", "") or label.replace("-", "") in squashed):
            return f"https://{d}"
        if tokens and sum(t in label for t in tokens) >= max(1, len(tokens) // 2):
            return f"https://{d}"
    return None
