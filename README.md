# AI Opportunity Pipeline

Give it a company name. Four agent stages research the company, diagnose its challenges with explicit reasoning, map AI opportunities to its real projects and operations, and write a one-page pitch to its CEO. Every run produces a **5-section assessment report**:

1. **Company Overview**: what they do, industry, scale, geographic presence
2. **Key Business Information**: offerings and projects, recent developments, expansion plans, public info (RERA, partnerships, financials)
3. **Potential Business Challenges**: operational, sales and customer experience, each with a `reasoning` field
4. **AI Opportunities**: ranked by a weighted rubric, each mapped to the challenges it solves and the projects or journey stage it applies to
5. **Personalized CEO Pitch**: one page covering (a) why we reached out, (b) the opportunities, and (c) the recommended solutions

Use it from the CLI or from the React web app (see **Web app** below).

```bash
python run_pipeline.py "Business Name" --url business.com
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your keys
```

| Key | Needed? |
|---|---|
| `GEMINI_API_KEY` | Yes, for the default provider (`LLM_PROVIDER=gemini`). Get one at Google AI Studio |
| `GEMINI_MODEL` | Optional, defaults to `gemini-3.8-flash` |
| `OPENAI_API_KEY` + `OPENAI_MODEL` | Only if `LLM_PROVIDER=openai` |
| `OPENROUTER_API_KEY` + `OPENROUTER_MODEL` | Only if `LLM_PROVIDER=openrouter`. Free `:free` models work on a free account, with a daily request limit |
| `TAVILY_API_KEY` | Optional, best search quality |
| `SERPER_API_KEY` | Optional, used if there's no Tavily key |
| none | Search falls back to DuckDuckGo automatically |

## Usage

```bash
python run_pipeline.py "Acme Dental"
python run_pipeline.py "Acme Dental" --url acmedental.com              # lock onto the right company
python run_pipeline.py "Acme Dental" --context "family dentist, Austin" # or disambiguate with text
python run_pipeline.py "Acme Dental" --from-step 3                     # reuse saved 01/02, rerun 3-4
python run_pipeline.py "Acme Dental" --provider openai
```

Outputs go to `outputs/<business-slug>/`:

| File | Written by |
|---|---|
| `01_business_profile.json` | Stage 1: Researcher |
| `02_business_challenges.json` | Stage 2: Challenge & Reasoning Analyst |
| `03_ai_opportunities.json`, `03_winning_strategy.json` / `.md` | Stage 3: AI Opportunity Strategist (ideation + rubric scoring) |
| `04_ceo_pitch.md` (+ `.json`) | Stage 4: CEO Pitch Builder (1-page pitch, then email, elevator pitch, ROI) |
| `04_prototype.html` | Stage 4, optional (`--no-prototype` / `BUILD_PROTOTYPE=false` skips it) |
| `05_assessment_report.json` / `.md` | **The 5-section report**, assembled in Python from the files above |
| `00_run_meta.json` | Orchestrator (tokens, cost, search providers used) |

## Web app (FastAPI + React)

Run the backend and the frontend in two terminals, both from this folder.

**Terminal 1, the API on port 8000:**

```bash
source .venv/bin/activate
uvicorn api.index:app --reload --port 8000
```

**Terminal 2, the React dev server on port 5173.** It proxies `/api` to port 8000.

```bash
cd frontend
npm install      # first time only
npm run dev
```

Open http://localhost:5173. **Saved reports** loads any run in `outputs/` without spending API credits. **Run analysis** streams live stage progress.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Provider, model, and whether keys are set (no API call) |
| `GET /api/examples` | List saved runs in `outputs/`, including partial ones |
| `GET /api/examples/{slug}` | A saved run as the 5-section JSON + Markdown + pitch text |
| `GET /api/examples/{slug}/prototype` | The run's HTML prototype |
| `POST /api/analyze/stream` | `{"company_name", "url"?, "include_prototype"?}` → Server-Sent Events: `stage` / `status` / `note` / `agent_done` / `result` / `error` |
| `POST /api/analyze` | Same input, with one JSON response at the end |

API docs are at http://127.0.0.1:8000/docs.

### Demo mode (no API quota)

The real app and pipeline, with fake model and search calls. Use it to try the UI, record a walkthrough, or test the live progress view.

```bash
python scripts/demo_api.py                                              # demo API on port 8010
cd frontend && API_PROXY_TARGET=http://127.0.0.1:8010 npm run dev -- --port 5174
```

Open http://localhost:5174.
- Each step takes about 2.5 seconds; change it with `DEMO_DELAY`.
- Stage 3 shows a model-fallback note.
- A company name containing "fail" stops at stage 3 the first time, so you can try **Resume**.
- Demo reports go to a temporary folder, never `outputs/`.

## Tests

```bash
pytest -q tests/                     # offline: pipeline, report, search, API (mocked Gemini + web), free, ~1 second
cd frontend && npm run build && cd ..  # type-check + production build of the web app
python tests/smoke_live.py            # live: real Gemini + search, needs GEMINI_API_KEY, costs credits
python tests/smoke_live.py "Blue Bottle Coffee" --url bluebottlecoffee.com
```

## How it's built

```
run_pipeline.py        orchestrator + CLI
agents/                researcher, strategist, evaluator, builder (+ base.py: context, file names)
prompts/               system prompts, one .md per LLM call — edit freely
utils/llm.py           Gemini (google-genai) / OpenAI behind one interface; validation + repair retries
utils/schemas.py       Pydantic models for every handoff
utils/search.py        Tavily → Serper → DuckDuckGo chain, homepage scrape, tech detection
utils/costs.py         token + cost tracking (edit PRICES_PER_MTOK for other models)
utils/console.py       rich spinners and summary tables
```

**Design choices**
- **Structured output:** Gemini calls pass `system_instruction`, `response_mime_type="application/json"` and `response_schema=<PydanticModel>` in `GenerateContentConfig`, and the JSON is validated into the same Pydantic model. OpenAI uses JSON mode plus Pydantic validation. Either way, an invalid or rule-breaking response is sent back to the model with the exact error, up to `MAX_VALIDATION_RETRIES` times.
- **Deterministic decisions:** the LLM scores each criterion from 1 to 10. Python computes the weighted totals, picks the winner, and does all the ROI math (totals, payback, 3-year ROI). Change the rubric weights in `.env`.
- **Search without a Tavily key:** DuckDuckGo uses an 8-second request timeout and one quick retry, runs at most 4 queries, and a provider that fails twice in a row is skipped for the rest of the run. Research also stops issuing queries after 75 seconds and continues with what it has.
- **Thin data:** if search returns little and the homepage is unreachable, the profile is forced to `data_quality: "low"`, inferences go into `assumptions`, and the pitch adds an "illustrative figures" caveat.
- **Resilience:** the google-genai client retries 408/429/5xx errors with backoff, tenacity adds retries around each call (including the streamed prototype), and a failed search provider falls through to the next one. Completed steps stay on disk, so `--from-step` resumes.
- **Safety blocks:** if Gemini blocks a prompt or stops a response for safety reasons, the run stops with a clear message instead of retrying.
- **Thinking:** `LLM_EFFORT` and `BUILDER_EFFORT` map to Gemini thinking levels (`minimal` → `MINIMAL` … `xhigh`/`max` → `XHIGH`). If a model doesn't accept a thinking level, the client drops it and retries automatically.
- **Models:** `GEMINI_MODEL` (default `gemini-3.8-flash`) runs every agent. Set `GEMINI_BUILDER_MODEL` to use a different model for Agent 4, e.g. `gemini-3.5-flash-lite` for a faster, cheaper run.
- **Cost:** token counts are always tracked, with thinking tokens counted as output. Dollar costs show as "n/a" until you set `PRICE_INPUT_PER_MTOK` / `PRICE_OUTPUT_PER_MTOK` in `.env` or add your model to `PRICES_PER_MTOK` in `utils/costs.py`.

## Evaluation results

Generated by `python scripts/eval.py`.

<!-- eval:start -->
| Company | Run | Similarity ↓ | Judge (0-100) | Reasoning | Research | Practicality | Specificity | Verified | Citations | Tokens in / out | Calls | Time |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Shivalik Group | legacy | 0.081 | — | — | — | — | — | — | — | 54,621 / 50,014 | — | — |
| Sobha Limited | legacy | 0.081 | — | — | — | — | — | — | — | 54,255 / 53,738 | — | — |

- **Similarity** is the mean cosine between this company's AI opportunities and every other company's (TF-IDF cosine, no API calls); lower means more company-specific. Overall: **0.081** over 42 cross-company pairs.
- **Judge** is not run (pass `--judge`). It scores the criteria a single report can show: reasoning (30), research (20) and practicality (20), renormalized to 0-100; specificity is reported but not weighted. AI tool usage, product quality and documentation are project-level and aren't judged per report.
- **Verified** is the Phase 3 verifier's pass rate over factual claims in the pitch (estimates excluded).
- **legacy** runs were saved before the Phase 1-6 upgrade: no per-stage tokens, verifier or citations.
- Skipped: adani-realty: HandoffError; blue-bottle-coffee: no AI opportunities yet
<!-- eval:end -->
