"""Decide which search results are worth reading in full (pure Python, no LLM).

Primary, recent sources win: exchange filings and the company's own investor material beat news,
news beats aggregators, and newer beats older. A couple of pages per domain at most, so one site
can't crowd out the rest.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from utils.dates import months_old, parse_as_of
from utils.search import SearchResult, domain_of

FILING_DOMAINS = ("nseindia.com", "bseindia.com", "sebi.gov.in", "sec.gov", "annualreports.com")
RERA_HINT = ("rera",)
NEWS_DOMAINS = (
    "economictimes", "livemint", "business-standard", "moneycontrol", "thehindubusinessline", "financialexpress",
    "reuters", "bloomberg", "ndtvprofit", "cnbctv18", "thehindu", "hindustantimes", "timesofindia", "forbesindia",
    "businesstoday", "zeebiz", "realty.economictimes", "constructionworld", "propequity", "techcrunch", "wsj", "ft.com",
)
LOW_VALUE = (
    "facebook.", "instagram.", "x.com", "twitter.", "youtube.", "pinterest.", "quora.", "reddit.",
    "glassdoor.", "indeed.", "ambitionbox.", "justdial.", "yelp.", "tripadvisor.",
)
INVESTOR_PATH = re.compile(r"investor|/ir/|presentation|transcript|earnings|quarterly|results|annual-report|"
                           r"operational-update|financial|shareholder|press-release|media", re.I)


@dataclass
class Candidate:
    result: SearchResult
    source_type: str        # filing | investor | rera | company | news | other
    published: str | None   # ISO date if one could be inferred
    score: float


def classify(result: SearchResult, company_domain: str | None) -> str:
    d = domain_of(result.url)
    url = result.url.lower()
    if any(f in d for f in FILING_DOMAINS):
        return "filing"
    if any(h in d for h in RERA_HINT):
        return "rera"
    own = company_domain and (d == company_domain or d.endswith("." + company_domain))
    if own and (INVESTOR_PATH.search(url) or url.endswith(".pdf")):
        return "investor"
    if url.endswith(".pdf") and INVESTOR_PATH.search(url + " " + result.title):
        return "investor"
    if own:
        return "company"
    if any(n in d for n in NEWS_DOMAINS):
        return "news"
    if any(x in d for x in LOW_VALUE):
        return "low"
    return "other"


TYPE_WEIGHT = {"filing": 10, "investor": 9, "rera": 7, "news": 6, "company": 5, "other": 3, "low": 0}


def rank_sources(results: list[SearchResult], company_domain: str | None, limit: int = 6,
                 per_domain: int = 2, exclude: set[str] | None = None) -> list[Candidate]:
    exclude = {u.rstrip("/").lower() for u in (exclude or set())}
    candidates: list[Candidate] = []
    for r in results:
        if not r.url or r.url.rstrip("/").lower() in exclude:
            continue
        kind = classify(r, company_domain)
        if kind == "low":
            continue
        published = parse_as_of(r.date) or parse_as_of(r.url) or parse_as_of(r.title)
        age = months_old(published)
        recency = 0.0 if age is None else max(0.0, 4.0 - age / 6)   # up to +4 for this month, 0 after 2 years
        candidates.append(Candidate(r, kind, published, TYPE_WEIGHT[kind] + recency))
    candidates.sort(key=lambda c: c.score, reverse=True)
    chosen: list[Candidate] = []
    per: dict[str, int] = {}
    for c in candidates:
        d = urlparse(c.result.url).netloc.lower()
        if per.get(d, 0) >= per_domain:
            continue
        per[d] = per.get(d, 0) + 1
        chosen.append(c)
        if len(chosen) >= limit:
            break
    return chosen
