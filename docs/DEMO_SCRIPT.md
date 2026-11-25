# Demo video script (about 8 minutes)

The assessment asks for a 5–10 minute walkthrough of **product, workflow, reasoning and decisions**. Reasoning is 30% of
the grade and research quality 20%, so reasoning gets the most time here (about 3 of the 8 minutes).

Spoken text is in plain paragraphs and is written to be read aloud, at a comfortable pace of about 140 words a minute.
Lines starting with **ON SCREEN** are what to show or click. Lines in [square brackets] are notes to you and are not spoken.

## Before you record (10 minutes)

1. **Pick the company for the live demo** and run it once beforehand, so you know it works and you've checked its CEO
   name and figures. This script uses *Prestige Group*; swap in whichever you've checked and say its name where the script does.
2. **Have these open in separate tabs**, in this order: the app's home page, a finished report for that company, the
   "How it works" page (`/?view=how-it-works`), `docs/APPROACH.md` on GitHub, and the Sobha reasoning story (section 5 of that
   page, "The wrong managing director").
3. **Record the live run separately.** A real run on free models can take several minutes. Start it, record the first minute
   of the timeline while you talk, then cut to the finished report. The script marks the cut.
4. **Screen at 1440×900 or similar, browser zoom 110%,** notifications off, a quiet room. Read the script once aloud first.
5. **If something fails on camera**, don't edit around it. Say the fallback line marked in the script, which is honest and
   fine to leave in.

---

## 0:00 to 0:30: What this is

**ON SCREEN:** the app's home page, "Research a company".

> Hi, I'm [your name]. For this assessment I built an AI research and recommendation agent. You give it a company's name, and
> it produces a cited intelligence report: what the company does, its challenges with my reasoning, ranked AI opportunities,
> and a one-page pitch to its CEO.
>
> The task says a working solution with strong reasoning beats a polished one with weak thinking, so I'll spend most of this
> video on the reasoning, and how I stopped the AI from making things up. First, a quick tour of the product.

---

## 0:30 to 2:30: The product

**ON SCREEN:** type `Prestige Group` in the box, open "Add website", enter `prestigeconstructions.com`, press Research.

> I'll research Prestige Group. Adding the website helps lock the research onto the right company.

**ON SCREEN:** the run timeline appears. Let it run for about 45 seconds while you talk.

> This is the run timeline. There are four stages: research, challenges, opportunities, and the pitch. Each shows its time,
> how many sources it read, and its token use, and the log lines underneath show what it's doing.

**ON SCREEN:** point at stage 1's log lines (results found, documents read).

> In the research stage it searches the web, picks up to six of the best pages or PDFs, and reads them in full. It prefers
> primary sources, like company filings and investor presentations, over news and blogs.

[CUT here. Continue on the finished report.]

**ON SCREEN:** the finished report, top of the page: name, one-line description, the two badges, the key-figures strip.

> Here's the finished report. At the top you can see the data quality, and a verification badge that I'll explain later.
> These key figures each carry a small citation and the date of the fact behind them.

**ON SCREEN:** hover a citation mark so the source popover appears.

> Every claim in this report links to a numbered source with its title, date and link, so you can check anything I say.

**ON SCREEN:** scroll to Challenges. Pause on the first one.

> The challenges section follows the task's structure: possible challenges, operational bottlenecks, sales, and customer
> experience. Each one has evidence, then my reasoning, then the business impact. The reasoning is what you asked me to explain.

**ON SCREEN:** scroll to Opportunities; click the top row so it expands.

> These are the AI opportunities, ranked. They aren't generic. Each one names the actual projects or operations it applies to.
> When I expand the top one, I get the problem, how the AI works, a build-versus-buy recommendation with real vendors, a
> thirty-sixty-ninety-day pilot with measurable targets, whether the data exists, and the compliance rules that apply. That's
> the practical side: what a team could start next month.

**ON SCREEN:** scroll to the CEO pitch; point at the A4 page, then open the Export menu.

> And this is the one-page pitch for the CEO. What you see is exactly what gets exported as a PDF. It opens with something the CEO
> has actually said, when a source has a quote I can verify word for word, and otherwise with the newest cited fact. Then it
> makes the case: why I'm reaching out, the opportunities, and what I'd recommend. I can also export the full report, a ten-slide deck, and an email draft. The email draft never sends anything. I
> choose the recipient and send it myself.

---

## 2:30 to 4:00: The workflow

**ON SCREEN:** the "How it works" page, the orbit diagram. Click a step or two.

> Here's the workflow. There are four stages that use language models, and one principle: the models read and write, and
> Python decides and checks.
>
> The research stage turns pages into dated facts. The challenges and opportunities stages reason from those facts. Scoring is
> split: the model gives each idea a score on five criteria, but Python does the arithmetic, the ranking, and a stress test
> of the ranking. The pitch stage writes the one-pager, and then a verifier checks it before anything is saved. The exports
> use no model at all.

**ON SCREEN:** switch to the architecture diagram in `docs/APPROACH.md`.

> This diagram is in my documentation. The reason for the split is simple: models are good at reading and writing, but they
> sometimes invent things, and they're unreliable at arithmetic. So anything that must be exact, like dates, figures,
> rankings and quotes, is done in code that I can test.

---

## 4:00 to 7:00: The reasoning (the most important part)

**ON SCREEN:** `docs/APPROACH.md`, section 2, the provenance diagram.

> The first design decision was about trust. Every fact the system uses gets an ID and a date. A figure from an investor
> presentation is, say, S3 dot F7, dated to the quarter it describes. If two sources disagree, the newest one wins and the
> older fact is marked as superseded, and the later stages are told not to use it. Facts about the same thing in different
> periods don't replace each other, so a quarterly number never overrides an annual one.
>
> There are three more rules. A leader's name is only used if a source from the last twelve months actually contains it. A
> figure that appears in no source gets removed. And a CEO quote is only kept if it appears word for word in the page it came
> from.

**ON SCREEN:** `docs/APPROACH.md`, section 5, "The wrong managing director".

> I added these rules because of a real failure. An early run for Sobha addressed the pitch to Francis Alfred as managing
> director. That was out of date: the current managing director, Jagadish Nangineni, was re-appointed in July 2026. The same pitch
> used FY2025 figures when FY2026 results were out, and its top idea rested on an assumed return on investment.
>
> The cause was that research only saw search snippets with no dates. Nothing checked who was current or which number was newest.

**ON SCREEN:** back to the report; scroll to the pitch and show the verification line, then the Trace panel; click a pitch line.

> Now three layers catch this. The research stage supersedes the old appointment. The pitch only opens on a CEO's quote if
> that person is in current leadership. And the verifier extracts every name, figure and period from the pitch and matches
> each to a fact. A former leader is replaced by their job title everywhere, and a stale figure is flagged with a pointer to
> the newer one. That's what this badge shows: how many factual claims in the pitch were backed by a source. Each of those
> cases has an automated test.
>
> The Trace panel lets you pick any line in the pitch and see the chain behind it: the facts, the challenge, and the
> opportunity it came from. If a line has no source, it says so instead of hiding it.

**ON SCREEN:** the Opportunities table, the Evidence and Score columns.

> The third fix was in the scoring. Ideas whose value rests on assumptions now score lower. Each idea lists the inputs its
> value depends on, and labels them as public data, an industry benchmark, or an assumption. Python discounts the return on
> investment by how much of it is backed by sources. Python also adds a criterion for how well the idea fits what the CEO has
> said and the company's core business, and then it re-ranks under conservative assumptions, and reports whether the winner
> still wins. So an assumption-heavy side project can't beat a core idea just because its numbers look big.

---

## 7:00 to 8:30: Decisions and close

**ON SCREEN:** `docs/AI_USAGE.md`, the model-choices table.

> A few other decisions. I used a cheap model for the high-volume reading work, like extracting facts, and the stronger
> model for reasoning and writing. Calls are capped, pages are cached, and tokens are logged per stage. In my runs that comes to
> seven to nine model calls per company.
>
> Vendors and compliance rules come from curated lists with official links, and the system drops any vendor or law the model
> suggests that isn't on the list. That means less coverage, but nothing invented.
>
> On tools: I built this with Claude Code, plus design skills for the interface. Inside the product it uses Gemini and
> OpenRouter models, and Tavily or DuckDuckGo for search. My documentation lists where the AI was wrong along the way, and how
> I caught it.

**ON SCREEN:** the README "With more time" section.

> It has limits, and I'd rather say so. The free models are rate-limited and sometimes overloaded, so some runs fail and
> need a retry. And my evaluation covers three companies on the final version, and I haven't run the scoring judge yet. The
> new pipeline also uses more tokens than my first version, because it reads whole documents. With more time I'd run and
> score every example company, add official stock-exchange filings and the state RERA
> registers as sources, and let a user mark a fact as wrong and re-run just the affected stages.
>
> Thanks for watching. The code, the documentation, and the live app are linked below.

---

## If something goes wrong on camera

| What happens | Say this, and keep going |
|---|---|
| A run fails or stalls | "Free models are rate-limited, so runs sometimes need a retry. Here's one I ran earlier." Then open the saved report. |
| The live app is slow to load | "The free host sleeps when idle, so the first load takes a moment." Wait it out. |
| A PDF export fails | "The free host has little memory, so PDFs can fail during a run. Here's the exported file." Then show a file you exported earlier. |
| You lose your place | Pause, breathe, and restart the sentence. You can cut it out afterwards. |

## Timing guide

Measured from the script: 1261 spoken words, about 9.0 minutes at a steady 140 words a minute, plus a few seconds
for clicks and pauses, so expect **9 to 10 minutes**: right at the task's 10-minute limit. Speak a little faster than 140,
or trim, to land near 9.

| Section | Speaking time | Words |
|---|---|---|
| What this is | 0.6 min | 90 |
| The product | 2.4 min | 342 |
| The workflow | 1.0 min | 141 |
| The reasoning | 3.2 min | 451 |
| Decisions and close | 1.7 min | 237 |
| **Total** | **9.0 min** | **1261** |

To trim about a minute, cut the sentence about email drafts, the last paragraph of the workflow section, and the line about
the figures strip. If you run short, spend longer on the Trace panel.
