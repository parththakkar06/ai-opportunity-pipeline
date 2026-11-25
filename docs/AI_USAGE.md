# How AI was used

Two different kinds of AI are involved. Keeping them apart is the point of this page:

1. **AI used to build the project:** a coding assistant and design skills.
2. **AI inside the product:** the models the pipeline calls at run time.

## 1. Tools and what they were used for

| Tool | Used for |
|---|---|
| **Claude Code** (Anthropic, Opus model), in the Claude desktop app | Planning (`docs/IMPLEMENTATION_PLAN.md`, `docs/DESIGN_DIRECTION.md`), writing the Python and React code, the offline test suite, browser checks of the UI (accessibility audit, responsive and keyboard passes), and the docs. Each phase was planned first, approved, built on its own git branch, tested (`pytest` + `npm run build`) and committed. |
| **Design skills** in `.claude/skills/` | `emil-design-eng` (motion: whether to animate, durations, easing), `apple-design` (type hierarchy, wayfinding, reduced motion), `web-design-guidelines` (accessibility and UI rules), `break-ui` (worst-case data review), and `ui-ux-pro-max` (the earlier frontend's design system). |
| **Google Gemini** (`gemini-3.8-flash` by default) | The default model provider for the pipeline. |
| **OpenRouter** free models (`google/gemma-4-31b-it:free`, with a fallback list) | An alternative provider that works on a free account. It's also the default **cheap model** for fact extraction, verification leftovers and the eval judge. |
| **OpenAI** (optional) | Supported behind the same interface (`LLM_PROVIDER=openai`). |
| **Tavily / Serper / DuckDuckGo** | Web search, in that order of preference. DuckDuckGo needs no key. Tavily's extract endpoint is a fallback for pages that block direct fetching. |

## 2. Model choices: cheap model for reading, strong model for reasoning

| Job | Model | Why |
|---|---|---|
| Turn a page or PDF into dated facts and verbatim quotes | cheap (`CHEAP_MODEL`) | High volume, low judgement. Batched 3 documents per call and cached per URL. |
| Profile, challenges, opportunities, rubric scores, decision memo, pitch | main (`GEMINI_MODEL` / `OPENROUTER_MODEL`) | Reasoning and writing quality matter here. |
| Pitch claims Python couldn't settle | cheap, at most 1 call | A yes/no/partial check against listed facts. |
| Eval judge | cheap, 1 call per report, cached | Scores reports on the assessment criteria. |
| Scoring maths, ROI, verification, citations, exports | **none**: Python | Must be exact and reproducible. |

Every structured call uses Pydantic schemas with JSON mode. If the output is invalid or breaks a business rule (for example "every idea needs a 30/60/90 pilot"), the exact problem goes back to the model for up to 2 repair attempts.

## 3. Key prompts

All prompts are in `prompts/`, one Markdown file per call. The rules that matter most:

- **Fact extractor** (`prompts/fact_extractor.md`): accuracy over coverage; one self-contained sentence per fact, with metric, value, period and date; Indian fiscal-year rules; "never use your own background knowledge". For CEO quotes: "copy the exact words… if you can't find exact words, return no quote". Python then checks each quote word for word anyway.
- **Researcher** (`prompts/researcher.md`): use only the evidence pack, never memory; cite fact IDs (`S3.F7`) per field; the newest source wins and superseded facts aren't cited; name leaders only from evidence.
- **Strategist** (`prompts/strategist.md`): every idea must solve a diagnosed challenge and name where it plugs in; vendors and compliance rules only from the supplied curated lists.
- **Evaluator** (`prompts/evaluator.md`): five criteria, including `ceo_relevance` (fit with the CEO's stated priorities and the core business); label each value driver as public data (with fact IDs), benchmark or assumption, because Python discounts assumptions.
- **Pitch builder** (`prompts/builder_pitch.md`): the opening line is written in Python and must not be reworded; no quotation marks except the verified quote; never attribute views to the CEO.
- **Verifier and judge** (`prompts/verifier.md`, `prompts/eval_judge.md`): judge only from the facts or report given; "if unsure, answer no".

## 4. Where the AI was wrong, and how it was caught

### The pipeline's models
| What went wrong | How it was caught | What stops it now |
|---|---|---|
| A Sobha pitch addressed a **former managing director** (Francis Alfred; the current MD, Jagadish Nangineni, was re-appointed in July 2026) | You spotted it in the report | The 12-month evidence rule, newest-wins superseding, and the verifier replacing unevidenced names with the title (`test_wrong_md_*`) |
| The same pitch used **FY2025 figures** when FY2026 results existed | You spotted it | Newest-wins per metric and period type; the verifier flags stale figures with the newer fact (`test_stale_fy2025_*`) |
| The **winning idea rested on assumed ROI** and wasn't core to the business | You spotted it | Evidence-adjusted ROI plus the CEO-relevance criterion (`test_sobha_assumption_heavy_*`) |
| Models can **invent vendors or cite laws from memory** | Planted in the fixtures: "DentalBot Pro", "gdpr" | Curated lists; Python drops anything not in them (`test_vendors_not_in_the_curated_list_are_dropped`) |
| Models **paraphrase quotes** as if they were verbatim | Tests with paraphrased quotes | Exact-substring check against the cached page (`test_paraphrased_or_trivial_quotes_are_rejected`) |
| A pitch can **state an ROI input as a fact** ("~100 missed visits a month") | The verifier in the fixture run | Factual paragraphs only count sourced figures; the claim is flagged, and the pass rate shows on the report |

### Claude Code (the coding assistant)
Its mistakes were caught by the offline tests it wrote, by running the UI in a real browser, or by you. Recording them honestly:

- **Misread errors as a used-up quota.** Gemini's `503`/`504` overloads looked like "the key hit its limit". Testing a different model with the same key showed the key was fine. The client now distinguishes `429 RESOURCE_EXHAUSTED` from overload errors.
- **Tavily `site:` bug.** Research sent a query that was only `site:adanirealty.com`, which Tavily rejects. Caught from a screenshot you sent; fixed, with a regression test.
- **A truthiness bug.** `months_old(...) or 99` treated a 0-month-old fact (a live company page) as 99 months old, so valid leaders were dropped. Caught by a new test.
- **Date parsing.** A timestamp like `2026-08-04T10:00` fell through to the "bare year" rule, and a bare current year was dated 31 December, in the future. Both caught by tests and a citation showing a future date.
- **Caching.** Documents the model returned nothing for weren't cached, so reruns paid again. Caught by the "rerun costs 0 extraction calls" test.
- **Small breakages.** An edit left an unterminated string; demo mode broke when a method gained a `cache` argument; a test patched a function and then called the patched version (infinite recursion). All caught immediately by the test run.
- **Front end:**
  - Lazy-loading dropped keyboard focus from the report title.
  - The redesign's scroll-spy was one section behind, because two scroll offsets stacked.
  - The A4 preview frame was blocked in the embedded browser.
  - Citation links nested inside a button, and links distinguished by colour alone (caught by the axe accessibility audit).
  - A long URL widened the page on phones (caught by the break-ui worst-case data).

## 5. What AI was not used for

- **Deciding the ranking, the ROI or what's true.** Python does those, from the evidence.
- **Exports.** The PDFs, deck and email are templates over saved data.
- **Sending anything.** The email draft never sends, and the To field starts empty.
- **Keys and credentials.** API keys live in `.env`, which is git-ignored and never committed.
