# Deploying to a private Hugging Face Space (free)

The same app that runs on your laptop, at one private URL that only your team can open. Cost: $0.
GitHub stays the source of truth; every push to `main` redeploys the Space automatically.

> Hugging Face's screens and free-tier limits change. Where a step names a menu, look for the closest match, and
> check their current pricing page for the free-tier limits before relying on them.

## How it fits together

```
GitHub (private repo)  ──push to main──▶  GitHub Action: test, then deploy
                                                │
                                                ▼
                                   Hugging Face Space (private, Docker)
                                   FastAPI + built React app + Chromium
                                                │  saves each finished run
                                                ▼
                                   Hugging Face Dataset (private): your saved reports
```

- **Private Space:** only members of your Hugging Face organization can open it (they must be signed in).
- **Keys:** model and search keys live in the Space's secrets, never in the repo.
- **Saved reports:** a free Space's disk resets when it restarts, so every finished run is also saved to a private
  Dataset and restored on startup (`utils/persist.py`).

## One-time setup (about 15 minutes)

### 1. Hugging Face
1. Create a free account at huggingface.co, then **create an organization** (for example `my-team`) and invite
   your teammates (free accounts are fine).
2. **New Dataset** in the org, set to **Private**, named e.g. `ai-opportunity-reports`. Leave it empty.
3. **New Space** in the org: name `ai-opportunity-studio`, SDK **Docker** (blank template), visibility **Private**, hardware
   **CPU basic (free)**.
4. **Create two access tokens** (Settings → Access Tokens), as fine-grained tokens if offered:
   - `github-deploy`: **write** access to the Space only. This goes into GitHub.
   - `space-reports`: **write** access to the Dataset only. This goes into the Space.

### 2. The Space's secrets
In the Space → **Settings → Variables and secrets**:

| Name | Kind | Value |
|---|---|---|
| `LLM_PROVIDER` | Variable | `openrouter` (or `gemini`) |
| `OPENROUTER_API_KEY` | **Secret** | your key (or `GEMINI_API_KEY` for Gemini) |
| `OPENROUTER_MODEL` | Variable | e.g. `google/gemma-4-31b-it:free` |
| `TAVILY_API_KEY` | **Secret** | optional; without it DuckDuckGo is used |
| `REPORTS_DATASET` | Variable | `my-team/ai-opportunity-reports` |
| `HF_TOKEN` | **Secret** | the `space-reports` token |

Any other setting from `.env.example` can be added the same way (`CHEAP_MODEL`, `MAX_DOCS`, `RUN_TIME_BUDGET_S`, ...).

### 3. GitHub
In your repo → **Settings → Secrets and variables → Actions**:

| Name | Kind | Value |
|---|---|---|
| `HF_TOKEN` | Secret | the `github-deploy` token |
| `HF_SPACE` | Variable | `my-team/ai-opportunity-studio` |

### 4. Deploy
Push to `main` (or run **Actions → Test and deploy → Run workflow**). The workflow runs the tests, then pushes to the
Space. The first build takes a few minutes (it installs Chromium). Open the Space page: when it says **Running**, the app
is live. Share that Space URL with your teammates.

## Using it
- Teammates sign in to Hugging Face, open the Space URL, and use the app exactly as you do locally.
- **Run another company:** type it in the box. Finished runs are saved to the Dataset automatically.
- **Seed it with reports you already have:** upload the run folders from your local `outputs/` (for example
  `outputs/sobha/`) into the Dataset's repo root. Skip `cache/`, which is rebuilt. They appear in **Saved reports**
  after the Space restarts.

## Limits and things to know
- **It sleeps when idle** and takes about a minute to wake on the next visit.
- **Free model keys are rate-limited, and the whole team shares yours.** If runs start failing, wait for the limit to
  reset or switch provider in the Space's variables.
- **Teammates spend your key.** Only add people you trust to the organization.
- **Resilience:** if the Dataset is unreachable, runs still complete; they're just not saved off the Space.
- **Rotate keys** that have ever been pasted into a chat or committed anywhere.

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Action fails at "Check the deploy settings" | `HF_SPACE` variable or `HF_TOKEN` secret not set in GitHub |
| Action fails at "Push to the Space" | The `github-deploy` token lacks write access to the Space, or `HF_SPACE` is misspelt |
| Space shows "Build error" | Open the Space's **Logs**; usually a typo in a variable or a failed `pip install` |
| App loads but runs fail immediately | Missing or wrong model key in the Space's secrets (the home page also shows a notice) |
| Reports disappear after a restart | `REPORTS_DATASET` / `HF_TOKEN` not set in the Space, or the token can't write to the Dataset |
| PDF export fails | Check the Space logs for Chromium errors; the Dockerfile installs it with `playwright install --with-deps chromium` |

## Run the same image locally (optional)
With Docker installed:

```bash
docker build -t ai-opportunity-studio .
docker run --rm -p 7860:7860 --env-file .env ai-opportunity-studio   # then open http://localhost:7860
```
