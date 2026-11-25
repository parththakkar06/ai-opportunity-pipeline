# Publishing a read-only snapshot on Vercel (free)

A fast, always-on site with your finished reports, their cited sources and every download (one-page pitch PDF, full
report PDF, deck, email draft, zip), behind a shared team password. **It is a snapshot: nobody can research a new
company on it.** For live runs, use the Hugging Face Space instead ([DEPLOY.md](DEPLOY.md)).

```
your computer                         GitHub (private repo)                 Vercel (free)
run companies locally  ──commit──▶   frontend/public/data/   ──push──▶   builds the static site
python scripts/build_static.py       (reports + PDFs + decks)             password prompt, then the reports
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
   - **Environment Variables:** add `SITE_PASSWORD` (the team password), for **all** environments.
     Optionally add `SITE_USER` to require a specific user name; otherwise any user name works.
   - Click **Deploy**.
4. **Open the site.** The browser asks for a user name and password: use any user name (or `SITE_USER`) and your
   `SITE_PASSWORD`. Share the URL and the password with the team.

## Updating the reports
Run a new company locally, run `python scripts/build_static.py`, commit `frontend/public/data`, and push. Vercel
redeploys by itself.

## How the password works, and its limits
`frontend/middleware.ts` asks for the password before serving anything, including `/data` and the downloads. With no
`SITE_PASSWORD` set it **refuses every request** instead of leaving the site open.
- It's a shared password, so anyone who has it can share it. The Hugging Face private Space checks each person's
  account instead.
- Vercel's own protection for production sites is a paid feature (as I last knew; check their pricing page).
- The middleware uses Vercel's Routing Middleware helper (`@vercel/functions`). It's covered by unit tests for the password
  logic, but it couldn't be run end to end without Vercel, so **after your first deploy, open the site in a private window and
  confirm it asks for the password.** If it doesn't, pause or delete the Vercel deployment straight away (Project → Settings) and tell me what you see.

## Troubleshooting
| Symptom | Cause |
|---|---|
| "This site is locked: set SITE_PASSWORD" | The environment variable is missing for that environment; add it and redeploy |
| Home page says "No reports have been published yet" | `frontend/public/data` wasn't committed, or the snapshot built zero runs |
| Build fails | Check the root directory is `frontend`; the log shows which command failed |
| A report is missing | It was legacy or unfinished; see the "skipped" lines when you run the builder |
| A download 404s | Rebuild the snapshot, then commit everything under `frontend/public/data` |

## Check it locally first (optional)
```bash
cd frontend && npm run build:static && cd dist && python3 -m http.server 8040   # open http://localhost:8040
```
(The password check only runs on Vercel.)
