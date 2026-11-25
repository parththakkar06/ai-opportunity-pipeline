# Vercel front end (free)

The Vercel site is the **live app's interface**: it calls the backend you run on Render
([DEPLOY_RENDER.md](DEPLOY_RENDER.md)) for research, saved reports and every export. There is no password.

```
Vercel (this site)  ──── API calls ────▶  Render (backend: research, reports, PDFs)
React interface                            FastAPI + Chromium, public
```

The two are separate sites, so Vercel must be told where the backend is, and the backend must allow calls from it
(`render.yaml` already sets `CORS_ORIGINS=*`; the API is public and uses no cookies).

## Setup (about 5 minutes)

1. **Backend first.** Deploy Render and note its address, for example `https://ai-opportunity-studio.onrender.com`.
2. **Vercel → your project → Settings → Environment Variables:** add
   - **Name:** `VITE_API_BASE`
   - **Value:** the Render address, with `https://` and no trailing slash
   - **Environments:** Production and Preview
3. **Redeploy** (Deployments → the latest → Redeploy). The address is baked in at build time, so changing it needs a new build.
4. Open the Vercel site. The home page should show "Research a company" and your saved reports.

Build settings come from `frontend/vercel.json` (`npm run build`, output `dist`); the Root Directory is `frontend`.

## What to expect
- **The first load can take up to a minute.** The free Render service sleeps when idle; the site says "Waking the server…"
  after 5 seconds, then continues by itself.
- **Everything works as on Render:** live research, the Trace panel, the A4 pitch preview, and downloads (the PDFs, deck
  and zip are served by Render, so they inherit its limits: see DEPLOY_RENDER.md).
- **Saved reports** live on the Render service and reset when it restarts, unless you've set up the Dataset persistence.
- **Anyone with the link can use it**, and runs spend your model key's quota. Keep to a free-tier key.

## Troubleshooting
| Symptom | Cause |
|---|---|
| "Can't reach the API" with `http://localhost…` or nothing shown | `VITE_API_BASE` isn't set, or it was added after the last build: set it, then redeploy |
| "Can't reach the server at https://…onrender.com" | The Render service is asleep (wait a minute and reload), stopped, or the address is wrong |
| Page loads but the browser console shows a CORS error | Render isn't running the latest `render.yaml` (`CORS_ORIGINS`); redeploy Render |
| Research form missing, "read-only snapshot" text | The build used `build:static`; Vercel should use `npm run build` (see `vercel.json`) |

## Optional: a static, read-only snapshot instead
If you'd rather have a fast site with no backend, `python scripts/build_static.py` bakes your current, finished reports
into `frontend/public/data`, and building with `npm run build:static` serves only those (no research, no waking up).
To use it on Vercel, set the build command to `npm run build:static` in the project's settings. The reports are then in
the repo, so keep it private.
