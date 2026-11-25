# Publishing a read-only snapshot on Vercel (free)

A fast, always-on site with your finished reports, their cited sources and every download (one-page pitch PDF, full
report PDF, deck, email draft, zip). **It is a snapshot: nobody can research a new
company on it.** For live runs, use the Hugging Face Space instead ([DEPLOY.md](DEPLOY.md)).

```
your computer                         GitHub (private repo)                 Vercel (free)
run companies locally  ──commit──▶   frontend/public/data/   ──push──▶   builds the static site
python scripts/build_static.py       (reports + PDFs + decks)             serves the reports
```

## What the team gets
- The same interface as the live app: report, Trace panel, A4 pitch preview, Export menu.
- Downloads of the files built ahead of time. The email draft works with Gmail, the Mail app and Copy; the `.eml`
  file has no recipient (the live app can set one, a static site can't).
- No typing a new company: the home page lists the published reports instead.

## One-time setup (about 10 minutes)

1. **Make the snapshot** on your computer, after running the companies you want to share:
   ```bash
   python scripts/build_static.py
   ```
   It bakes every *current, finished* run in `outputs/` into `frontend/public/data/`. Runs saved before the fact checks
   ("legacy") and unfinished runs are skipped unless you add `--include-legacy`; use `--only sobha,adani-realty` to pick runs.
   Needs Chrome installed (the PDFs are built with it). **Read the reports before sharing them.**
2. **Commit and push** `frontend/public/data` to GitHub. Keep the repo **private**, since the research is in it.
3. **Vercel:** sign up at vercel.com with your GitHub account (the free *Hobby* plan), then **Add New → Project** and import the repo.
   - **Root Directory:** `frontend`
   - Build settings come from `frontend/vercel.json` (it builds with `npm run build:static`), so leave the defaults.
   - No environment variables are needed.
   - Click **Deploy**.
4. **Open the site** and share the URL with the team.

## Updating the reports
Run a new company locally, run `python scripts/build_static.py`, commit `frontend/public/data`, and push. Vercel
redeploys by itself.

## Who can open it
**Anyone who has the link.** There is no password: the site is a static snapshot, so there are no keys and no backend
to abuse, and what it shows is research built from public sources. Every page is marked `noindex`, so search engines
are asked not to list it, but a forwarded link works for anyone.
- To limit access, use Vercel's own protection (Project → Settings → Deployment Protection; as I last knew, protecting a
  production site is a paid feature, so check their pricing), or use the private Hugging Face Space ([DEPLOY.md](DEPLOY.md)),
  which checks each person's account.
- Keep the **GitHub repo private**: the reports are committed in it.
- If you ever want a shared password back, add a Vercel Routing Middleware file that checks one (`frontend/middleware.ts`)
  and set it as an environment variable.

## Troubleshooting
| Symptom | Cause |
|---|---|
| Home page says "No reports have been published yet" | `frontend/public/data` wasn't committed, or the snapshot built zero runs |
| Build fails | Check the root directory is `frontend`; the log shows which command failed |
| A report is missing | It was legacy or unfinished; see the "skipped" lines when you run the builder |
| A download 404s | Rebuild the snapshot, then commit everything under `frontend/public/data` |

## Check it locally first (optional)
```bash
cd frontend && npm run build:static && cd dist && python3 -m http.server 8040   # open http://localhost:8040
```
