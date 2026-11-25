# Running the full app on Render (free, public)

The whole app on one Render URL: the interface, live research on any company, saved reports and every export. There is
**no password**, so anyone with the link can use it.

You don't install or learn Docker. Render builds the app itself from the `Dockerfile` already in the repo (it's what
bundles Chromium for the PDF exports and Node to build the interface).

## Read this first: it's public, and it runs on your key
Anyone who gets the link can start research runs, and every run spends your model key's quota.
- **Use a free-tier key with no card attached** (for example a free OpenRouter account), so the worst case is a used-up
  free quota and nothing is billed.
- Share the link only with the people who should have it. To take it offline, suspend the service in Render.

## Setup (about 10 minutes)
1. **Push the repo to GitHub** (`git push origin main`), then sign up at render.com with your GitHub account.
2. In Render: **New → Blueprint**, pick this repo and branch `main`. Render reads `render.yaml` (a free Docker web service).
3. It asks for one value: **`OPENROUTER_API_KEY`**. Paste a key from openrouter.ai (a freshly created one, never one you've
   pasted into a chat). Click **Apply**.
4. Wait for the first build, which takes several minutes because it installs Chromium. When the service shows **Live**,
   open its `https://….onrender.com` URL. Share that link.

Optional settings, added later under the service's **Environment** tab:

| Name | What it does |
|---|---|
| `TAVILY_API_KEY` | Better search. Without it, DuckDuckGo is used |
| `OPENROUTER_MODEL` | A different model. The default is `google/gemma-4-31b-it:free` |
| `LLM_PROVIDER` + that provider's key | `gemini` + `GEMINI_API_KEY`, or `openai` + `OPENAI_API_KEY` and `OPENAI_MODEL` |
| `REPORTS_DATASET` and `HF_TOKEN` | Keep saved reports across restarts in a private Hugging Face Dataset (see below) |

## What to expect on the free plan
(As I last knew Render's free tier; check their current terms.)
- **It sleeps after about 15 minutes idle.** The first visit afterwards takes up to a minute to wake the app.
- **Saved reports don't survive a restart.** The free disk resets whenever the service sleeps or redeploys, so the
  "Saved reports" list starts empty each time. To keep reports, create a private Hugging Face Dataset and a write token for it
  (steps 1–2 and 4 of [DEPLOY.md](DEPLOY.md)), then add `REPORTS_DATASET` and `HF_TOKEN` here. For a one-off test you can skip this.
- **Memory is small (about 512 MB).** A PDF export, which launches Chromium, may fail if it happens during a research
  run. The page, deck, email and `.eml` still work. Try the PDF when no run is in progress.
- **Free models are rate-limited and sometimes overloaded**, so a run can fail and need a retry.

## Updating it
Every push to `main` redeploys the service automatically (`autoDeploy: true`).

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Build fails | Open the service's **Logs**; send me the last 20 lines |
| The page loads but research fails right away | Missing or wrong `OPENROUTER_API_KEY` (the home page also shows a notice) |
| Very slow first load | The free service was asleep |
| PDF export fails | Out of memory; retry when no run is in progress |
| "Saved reports" is empty | The disk reset; see the persistence option above |
