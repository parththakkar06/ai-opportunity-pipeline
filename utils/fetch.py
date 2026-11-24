"""Fetch the full text of a web page or PDF (filings, investor decks, transcripts, news).

Plain httpx first (works with no API keys). If that's blocked or returns too little text and a
Tavily key is configured, Tavily's extract endpoint is tried. Text is capped per document.
"""
from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass
from datetime import date

import httpx

from utils.dates import parse_as_of

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36 AIOpportunityPipeline/1.0")
MAX_CHARS = 12_000
MAX_PDF_PAGES = 15
MIN_USEFUL_CHARS = 400


@dataclass
class FetchedDoc:
    url: str
    title: str
    text: str
    kind: str                 # html | pdf
    published: str | None     # ISO date found in the document/meta, if any
    retrieved: str            # ISO date the document was fetched
    via: str                  # httpx | tavily
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.text) >= MIN_USEFUL_CHARS

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FetchedDoc":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})


def _clean(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _html_to_text(html: str) -> tuple[str, str, str | None]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    published = None
    for attrs in ({"property": "article:published_time"}, {"name": "date"}, {"name": "publish-date"},
                  {"itemprop": "datePublished"}, {"name": "pubdate"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            published = parse_as_of(tag["content"])
            if published:
                break
    if not published:
        t = soup.find("time")
        if t:
            published = parse_as_of(t.get("datetime") or t.get_text(" ", strip=True))
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    return title, _clean(main.get_text("\n", strip=True)), published


def _pdf_to_text(data: bytes) -> tuple[str, str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - one bad page shouldn't sink the document
            continue
    title = ""
    try:
        title = (reader.metadata.title or "") if reader.metadata else ""
    except Exception:  # noqa: BLE001
        pass
    return title, _clean("\n".join(pages))


def fetch_document(url: str, timeout: float = 12.0, tavily_client=None) -> FetchedDoc:
    today = date.today().isoformat()
    doc = FetchedDoc(url=url, title="", text="", kind="html", published=None, retrieved=today, via="httpx")
    try:
        resp = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*"},
                         follow_redirects=True, timeout=timeout)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "").lower()
        if "pdf" in ctype or str(resp.url).lower().endswith(".pdf"):
            doc.kind = "pdf"
            doc.title, doc.text = _pdf_to_text(resp.content)
        else:
            doc.title, doc.text, doc.published = _html_to_text(resp.text)
    except Exception as exc:  # noqa: BLE001 - reported on the doc; Tavily may still succeed
        doc.error = f"{type(exc).__name__}: {str(exc).splitlines()[0][:120] if str(exc) else ''}".strip()

    if not doc.ok and tavily_client is not None:
        try:
            data = tavily_client.extract(urls=[url], extract_depth="basic", format="text", timeout=timeout + 10)
            items = data.get("results") or []
            if items and (items[0].get("raw_content") or "").strip():
                doc.text = _clean(items[0]["raw_content"])
                doc.via, doc.error = "tavily", None
        except Exception as exc:  # noqa: BLE001
            doc.error = (doc.error or "") + f" | tavily: {type(exc).__name__}"

    doc.text = doc.text[:MAX_CHARS]
    if not doc.published:
        doc.published = parse_as_of(doc.title) or parse_as_of(url)
    if not doc.ok and not doc.error:
        doc.error = "too little readable text"
    return doc
