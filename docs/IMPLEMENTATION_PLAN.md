> **Status (Nov 25, 2026):** Phases 1-10 are implemented, each on its own branch `upgrade/phase-N-*`; Phase 11 (final review) is in progress. Where the build differs from this plan, see the deviations noted at the end of each phase's report and `docs/DESIGN_DIRECTION.md` §11.

# Implementation plan: assessment upgrade (Phases 1–11)

**Status:** approved and implemented (see the note above). Each phase is implemented separately, then tested (`pytest -q tests/` and `npm run build`) before the next one starts.

**Baseline** (saved runs, OpenRouter `baidu/ernie-5.5-flash-preview:free`):
- About **54k input + 52k output tokens per run**, in about 7–8 model calls.
- Research reads search **snippets only**.
- The pitch is not verified.

**Kept unchanged:**
- Pydantic handoffs with repair retries
- Python scoring and ROI math
- the Tavily → Serper → DuckDuckGo search chain
- SSE progress streaming
- `--from-step`
- demo mode
- offline tests

---

## Cross-cutting (built in Phase 1, used by every later phase)

| Item | Design |
|---|---|
| **Cheap model** | New setting `CHEAP_MODEL`, used for page summaries, gap analysis, the verifier fallback, and the eval judge. Default: `OPENROUTER_CHEAP_MODEL=google/gemma-4-31b-it:free`, or `GEMINI_BUILDER_MODEL` when `LLM_PROVIDER=gemini`. The main model keeps reasoning (challenges, strategy, pitch). |
| **Disk cache** | `outputs/<slug>/cache/` holds `search/<sha1(query)>.json`, `pages/<sha1(url)>.{txt,meta.json}`, and `facts/<sha1(url)>.json` for the cheap-model fact lists. Reruns and `--from-step` re-use it, so repeating research costs 0 tokens. `--refresh` ignores the cache. |
| **Token log per stage** | `00_run_meta.json` gains `stages: {1: {input, output, calls, seconds}, …}` plus `budget: {pages_fetched, gap_round, verifier_calls}`. The CLI summary table and the UI "Run details" popover show it. |
| **Time-box** | Research has a hard budget of `RESEARCH_TIME_BUDGET_S=120`, covering search, fetch and gap-fill. The whole run has a soft budget of `RUN_TIME_BUDGET_S=600`, after which the prototype is skipped. Elapsed time is shown in the summary. |
| **Request count** | Matters on free tiers. Target **≤ 12 calls per run**:<br>• 6 page summaries batched into 2 calls<br>• 1 gap analysis<br>• 1 profile update<br>• the existing 5<br>• 0–1 for the verifier<br>Roughly +4–5 calls over today. |
| **No-key path** | DuckDuckGo plus plain `httpx` page fetches must keep working with no keys. Tavily `extract` is used only when a key is present. |

---

## Phase 1: Deep research
**Goal:** facts come from full documents, carry sources and dates, and are never filled from model memory.

1. **Source picking (Python, no LLM).** Rank search results by source type: exchange filings (nseindia, bseindia), the company's investor-relations pages and PDFs (investor presentations, quarterly updates, earnings-call transcripts), RERA portals, then reputable news. Also prefer **recency**: parse dates from snippets and URLs, newest first. Take the **top 6**. Add targeted queries such as `"<company>" investor presentation pdf`, `"<company>" Q* FY27 operational update`, `"<company>" earnings call transcript` and `site:<domain> investor`.
2. **Full-text fetch.** `httpx` fetches HTML and runs it through BeautifulSoup to get text. PDFs go through **`pypdf`** (new dependency), first ~15 pages. Tavily `extract` is used when a key exists. Each document is capped at about 12k characters before summarizing. Time-boxed and cached.
3. **Cheap-model fact extraction.** Each document becomes a `SourceDoc {source_id: "S1"…, url, title, type, published_date}` plus up to 25 `Fact {fact_id: "S3.F7", statement, number?, unit?, period?, as_of, source_id}`. Docs are batched 3 per call. **Main agents never see raw page text,** only fact lists plus snippets, still capped at 30k characters.
4. **Profile with provenance.**
   - `BusinessProfile` fields get `evidence: [fact_id]` and `as_of`. In practice, key fields (revenue, bookings, portfolio, leadership, projects, news, expansion, public info) become small `Sourced[...]` objects.
   - Python enforces **newest source wins**.
   - **Leadership:** a name survives only if backed by a fact dated within 12 months. Otherwise it becomes `"unknown"` and is recorded in `assumptions`. This is the wrong-MD fix.
5. **One gap-filling round, skipped when `data_quality == "high"`.**
   - The cheap model lists missing, stale or low-confidence fields, along with follow-up queries.
   - The pipeline runs at most 4 queries and fetches at most 2 extra docs, staying within 6 total.
   - The main model updates the profile once.
6. **Files:**
   - **New:** `utils/fetch.py`, `utils/cache.py`, `utils/sources.py` (ranking and dates), `prompts/fact_extractor.md`, `prompts/gap_analyst.md`.
   - **Changed:** `agents/researcher.py`, `utils/schemas.py`.
7. **Tests (fixtures, offline):**
   - PDF and HTML fixtures go through extraction.
   - The cache hit path costs 0 calls.
   - Stale leadership (more than 12 months old) becomes `"unknown"`.
   - Newest-wins merging.
   - The gap round is skipped when data quality is high.
   - The no-key DuckDuckGo path works.
   - Token log fields are filled in.

**Risk:** NSE and BSE often block automated fetches. Expect company investor-relations PDFs, transcript sites and news to do most of the work. Failures are logged as notes, not silent.

## Phase 2: CEO voice
1. **No new LLM call.** The fact extractor's schema gains `leader_statements: [{speaker, role, quote, topic, date, source_id}]`. That's free, since it runs in the same call.
2. **Quotes must be verbatim.** Python checks every `quote` is an exact substring, after whitespace normalization, of the cached source text. Non-matching quotes are dropped, so the model cannot invent a quote.
3. **Stated priorities.** Python builds `stated_priorities` (topic, quote, speaker, date, source) from the newest statements by the CEO or MD and saves them in `01_business_profile.json`.
4. **The pitch opens on one stated priority,** for example "On your Q4 FY26 call you said…", citing its `source_id`. If no verifiable statement exists, the pitch opens on the newest cited fact, and the report says "no CEO statements found".
5. **Tests:** the substring check rejects a paraphrased quote, the pitch-opening rule, and the fallback.

## Phase 3: Verifier (runs before the report is written)
1. **Python first, no LLM.** Extract every person name (from the `addressed_to` and leadership patterns), number (₹/$/%/crore/sq ft) and date or period (FY26, Q1 FY27, months) from the pitch fields. Match each against the cited facts and the stated priorities.
2. **Cheap model only for leftovers.** One call, at most, checks the unresolved claims: "Is claim X supported by facts [..]? yes / no / partial".
3. **Outcomes:**
   - Unsupported names are **replaced** with the title only ("Managing Director").
   - Unsupported numbers are **removed or flagged** in `04_verification.json`, listing each claim with its status and evidence.
   - The pass rate shows on the report, the UI badge, the exports and in evals.
4. **Tests:**
   - The **wrong-MD regression**: "Francis Alfred" with no recent evidence is replaced.
   - A stale FY2025 number is flagged when an FY2026 fact exists.
   - A supported number passes.
   - The pass-rate math.

## Phase 4: Better scoring (pure Python plus one extra criterion in the existing scoring call)
1. **New criterion `ceo_relevance` (1–10).** The evaluator scores alignment with `stated_priorities` and the core business (for example, the residential-sales share for Sobha). Weights move to `.env`. Proposed defaults: ROI 30, CEO relevance 25, feasibility 20, speed 15, moat 10.
2. **Confidence adjustment.** Each opportunity's ROI score is shrunk by the share of its value drivers labelled `assumption` versus `public data`: `adj = roi × (0.6 + 0.4 × evidence_share)`.
3. **Sensitivity check.** Re-rank under conservative settings (low value estimates, ROI confidence-adjusted, feasibility −1 for high-effort ideas). Output `winner_stable: bool` and the rank changes, shown in the report.
4. **Rejected ideas keep a one-line "why not"** from `why_not_the_others`, which already exists. It's shown muted in the ranking.
5. **Tests:**
   - Weights summing to 1.
   - The confidence adjustment.
   - Sensitivity flips when expected.
   - The **Sobha regression**: an assumption-heavy, non-core idea (EPC review) no longer wins over a core residential-sales idea, using a fixture.

## Phase 5: Practicality (same strategist call, schema only)
Each `AIOpportunity` gains:
- **`build_vs_buy`:** `{decision: build|buy|hybrid, vendors: [..], rationale}`. **Vendors must come from a curated list** in `data/vendors.yaml`, organized by market and category (India real estate CRM: Salesforce, LeadSquared, Sell.Do; messaging: WhatsApp Business API; and so on). Python drops any vendor not on the list, so the model can't invent one. Each list entry carries a URL so it can be checked.
- **`pilot_30_60_90`:** three milestones with KPIs and targets.
- **`data_readiness`:** each required data source rated `have / likely / missing`, with the reason.
- **`compliance`:** notes (DPDP Act 2023 consent and purpose limits, RERA advertising and disclosure rules, TRAI DLT for SMS) where relevant, drawn from a curated `data/compliance.yaml` so it isn't free text from memory.

**Tests:** vendor filtering, schema validation, and the fixture update.

## Phase 6: Traceability
1. **Citations everywhere.** Every rendered claim carries `[n]`, mapped to `source_id`, URL, title and date.
   - Challenge `signals` become fact references.
   - Opportunities reference challenges plus facts.
   - Pitch sentences carry `evidence` arrays, from the Phase 3 output.
2. **Report outputs.** `05_assessment_report.json` gains `citations[]` and a `trace` graph: fact → challenge → opportunity → pitch line.
3. **UI:**
   - Superscript citations with a hover or focus popover showing title, date and link.
   - A "Trace" view: pick a pitch line or opportunity to highlight its chain.
4. **Markdown and PDF:** numbered footnotes.
5. **Tests:** every pitch sentence has at least one resolvable citation; no orphan citation IDs.

## Phase 7: Evals (`scripts/eval.py`, runs on saved outputs only)
| Metric | Method | Cost |
|---|---|---|
| (a) cross-company similarity | Embeddings of opportunity titles and mechanisms, mean pairwise cosine across companies; lower is more company-specific. **Proposed:** Gemini `text-embedding` if a key is set, otherwise a dependency-free TF-IDF cosine in Python (noted in the output). | ~0–1 call per company |
| (b) LLM judge | The cheap model scores each report against the assessment rubric (30/20/20/15/10/5), with a short rationale. | 1 call per company |
| (c) verifier pass rate | Read from `04_verification.json` | 0 |
| (d) tokens per run | Read from `00_run_meta.json` | 0 |

The results table is written to `docs/eval_results.md` and the README.

**Needs fresh runs** with the new pipeline for Adani Realty, Sobha, Prestige, Brigade, Puravankara and Shivalik: about 6 runs at ≤ 12 calls each, so roughly 70 free-tier requests. Spread over two days if the daily cap is hit. Runs saved before Phase 1 are marked `legacy`.

## Phase 8: One-click exports (no LLM; works in demo mode)
**Backend:** `api/exports.py` and `utils/export/`. Endpoints `GET /api/examples/{slug}/export/{pptx|report.pdf|pitch.pdf|email|eml|zip}`. CLI: `--export` writes the `06_*` files.

1. **Deck (python-pptx):**
   - 10 slides, 16:9, as specified.
   - Accent colour from `brand.primary_color_hex` (fallback ink blue).
   - At most 6 bullets per slide, with speaker notes.
   - Citations on the Sources slide.
2. **Full report PDF:**
   - Jinja2 template → Playwright Chromium `page.pdf` (A4, cover with the verifier pass rate, table of contents, page numbers, footnoted dated citations).
   - Falls back to WeasyPrint, then to **system Chrome headless**, which is already installed on this Mac.
3. **One-page pitch PDF:** exactly 1 page (the test checks the page count with pypdf). Body text is ≥ 10pt; if it overflows, it re-renders from `ceo_pitch.short_version`, which the pitch builder writes in the same call.
4. **Email:**
   - The ~150-word body comes from the existing pitch fields, not a new call.
   - Buttons: **Open in Gmail** (compose URL), **Open in Mail app** (`mailto:`, checked to stay under 1,800 characters after encoding), and **Copy**.
   - **Download .eml** with the one-page PDF attached (`EmailMessage`).
   - The To: field is editable and empty by default. Nothing is ever sent.
5. **Download all (.zip).**
6. **Dependencies:** `python-pptx`, `jinja2`, `playwright`, `pypdf`. The README gets `playwright install chromium`.

**Tests:** slide count, notes and bullet limits; PDF page count (1 for the pitch); `.eml` parses and has the attachment; mailto length; zip contents. All run against demo fixtures.

## Phase 9: Frontend redesign (two steps)
1. **First:** write `docs/DESIGN_DIRECTION.md` (tokens, type scale, spacing, component list, motion), using the `emil-design-eng`, `apple-design` and `web-design-guidelines` skills. **Wait for approval.**
2. **Then build it.** Paper theme, Newsreader (or Source Serif 4) with Inter, a scroll-spy table of contents replacing the tabs, the command-bar intake, a calm run timeline, an A4 pitch preview, and the export menu.
   - Removes the template look you listed.
   - Keeps everything earned in phases 1–6 of the earlier frontend work: tokens, URL state, accessibility, the print stylesheet, lazy loading, keyboard paths.
3. **Finally:** a `break-ui` review, then the axe audit, responsive sweep and keyboard pass again.

## Phase 10: Documentation
- **`docs/APPROACH.md`:**
  - Mermaid diagrams of the stages, data flow, cache, verifier and exports.
  - Decisions and trade-offs.
  - The token budget.
  - Challenges and how they were solved, including the wrong-MD story and the verifier catching it.
- **`docs/AI_USAGE.md`:**
  - Tools used and what for.
  - Key prompts.
  - Where the AI was wrong and how it was caught (wrong MD, stale FY figures, Tavily `site:` bug, 503/429 quotas, lazy-load focus regression).
  - The cheap versus strong model split.
- **README:** 2-minute quickstart, demo mode, eval table, tokens per run, screenshots, and "with more time".

## Phase 11: Final review
1. **Strict self-assessment** against the rubric: top 10 weaknesses, then fixes.
2. **Clean-clone test:** a fresh clone into a temporary folder, following the README only, in demo mode (no keys). Everything must work, exports included.

---

## Proposed order and checkpoints
1 → 2 → 3 → 4 → 5 → 6 → **re-run the 6 companies** → 7 → 8 → 9 (design doc, approval, then build) → 10 → 11.
- **Why exports come before the redesign:** they're backend work, and the redesign's export menu needs those endpoints.
- **Demo-mode fixtures** are updated in each phase, so demos and tests never need keys.

## Deviations from the brief (proposed)
1. **Fact extraction is batched 3 documents per call** instead of one call per document, to keep free-tier request counts down. The token budget is the same.
2. **CEO quotes come from the same extraction call,** with no separate stage.
3. **The verifier is Python-first,** and uses the cheap model only for claims Python can't resolve (0–1 calls).
4. **Vendor and compliance lists are curated files,** so recommendations can't contain invented vendors or regulations.
5. **The PDF fallback chain is Playwright → WeasyPrint → system Chrome,** because WeasyPrint needs native libraries that a clean macOS install doesn't have.
