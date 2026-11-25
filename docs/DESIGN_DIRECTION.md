# Design direction: AI Opportunity Studio

**Status:** proposal for approval (Phase 9, step 1). Nothing in the UI changes until this is approved.

## 1. Intent

**A serious analyst brief, not a SaaS template.** It should read like a well-set research note that happens to be interactive.

The test for every element: does it help a reader trust and act on the findings? If it only decorates, it goes.

The skills applied:
- **emil-design-eng:** decide whether anything should animate at all, keep durations short, use strong ease-out curves, and never animate keyboard actions.
- **apple-design:** build hierarchy from type, not boxes; give clear wayfinding; respect reduced motion; size tracking by type size.
- **web-design-guidelines:** visible focus, AA contrast, semantic structure, and URLs you can deep-link.

## 2. What goes, and what replaces it

| Remove | Replace with |
|---|---|
| Slate-900 + sky-400 palette, glows | Warm "paper" theme, near-black ink, one neutral grey scale, one accent |
| Cards nested in cards, `rounded-2xl` everywhere | Hairline rules and whitespace. At most one level of container. 4px radius on controls only |
| Tiny uppercase letter-spaced eyebrow labels | Sentence-case labels in the UI face at normal tracking, or none at all |
| Sparkle logo, initials chips | A serif wordmark. Example companies become plain text links |
| Duplicated Copy / Print buttons | One **Export** menu, which holds copy, print, files and the email draft |
| Model id in the header | A small **Run details** popover: provider, models, tokens per stage, time, sources read |
| Data-less hero | With no report open: one centred input. With a report open: a metrics strip of real, cited figures |
| Five tabs | One scrolling document with a sticky, scroll-spied table of contents |

## 3. Tokens

All colours are CSS custom properties. Components never use raw hex values or Tailwind palette names.

### 3.1 Colour, light ("paper", the default)

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--paper` | `#FBFAF7` | Page background | — |
| `--sheet` | `#FFFFFF` | The A4 pitch preview, popovers, inputs | — |
| `--tint` | `#F3F1EC` | Hover rows, the expanded table row, code | — |
| `--ink` | `#17181A` | Body text, headings | 17.0:1 on paper |
| `--ink-2` | `#3E4046` | Secondary text | 9.9:1 |
| `--ink-3` | `#61646B` | Meta text, captions, muted "why not" | 5.7:1 (5.3:1 on tint) |
| `--rule` | `#E6E2DA` | Hairline dividers | decorative |
| `--rule-strong` | `#CFCAC0` | Input borders, table header rule | decorative (pairs with a text label) |
| `--accent` | brand colour, or `#1F3A6E` (ink blue) | Links, citation marks, active TOC item, focus ring, primary button | 10.7:1 for the fallback |
| `--on-accent` | `#FFFFFF` | Text on a primary button | 11.1:1 on the fallback |
| `--positive` | `#2E6B3B` | "Verified", "holds" | 6.1:1 |
| `--caution` | `#8A5300` | "No source", stale, partial | 6.1:1 |
| `--negative` | `#A3322A` | Errors, "replaced" | 6.6:1 |

**Brand accent rule (Python and TypeScript, same logic).** Take `brand.primary_color_hex`. Darken it in OKLCH lightness steps until it reaches at least 4.5:1 on both `--paper` and `--sheet`, then use that value. If there's no brand colour, or it can't reach 4.5:1 without turning to grey (chroma below 0.03), use ink blue. The accent is the only saturated colour on the page.

### 3.2 Colour, dark (secondary; follows the system or the toggle)

| Token | Value | Contrast |
|---|---|---|
| `--paper` | `#151518` | — |
| `--sheet` | `#1D1D21` | — |
| `--ink` / `--ink-2` / `--ink-3` | `#ECEAE4` / `#C9C6BF` / `#9E9B94` | 15.2 / 10.7 / 6.6 :1 |
| `--accent` (fallback) | `#8FB0E8` | 8.3:1 |
| `--positive` / `--caution` / `--negative` | `#7FC08C` / `#E2B15C` / `#EE8A80` | ≥ 7.4:1 |
| `--rule` / `--rule-strong` | `#2A2A2F` / `#3A3A40` | decorative |

In dark mode the brand accent is lightened by the same rule until it reaches 4.5:1. The A4 pitch preview stays white paper in both themes, because it is a picture of the printed page.

### 3.3 Type

- **Display and reading faces:** Newsreader (variable, optical sizing) for the wordmark, the company name, section headings and the pitch. Source Serif 4 is the fallback.
- **UI face:** Inter (variable) for controls, tables, meta text and labels.
- **Hosting:** both fonts are self-hosted via `@fontsource-variable/*`, so there's no request to Google and no layout shift. `font-display: swap`, with metric-matched fallbacks.
- **Numbers:** `font-variant-numeric: tabular-nums` on every figure, table and score.
- **Measure:** prose is capped at **68–72ch**. Tables can run wider, up to 960px.

| Role | Face | Size / line-height | Tracking | Weight |
|---|---|---|---|---|
| Wordmark | Newsreader | 20 / 24 | -0.01em | 600 |
| Company name (h1) | Newsreader | clamp(32px, 4vw, 44px) / 1.08 | -0.02em | 560 |
| Section heading (h2) | Newsreader | 26 / 1.2 | -0.015em | 560 |
| Item heading (h3) | Newsreader | 19 / 1.3 | -0.005em | 600 |
| Body (prose) | Newsreader | 17 / 1.6 | 0 | 400 |
| Pitch body (A4) | Newsreader | 10.5pt / 1.45, exactly as exported | 0 | 400 |
| UI / table | Inter | 14 / 1.45 | 0 | 400 / 500 |
| Meta / caption | Inter | 13 / 1.4 | 0.005em | 400 |
| Figure in the metrics strip | Inter | 24 / 1.1, tabular | -0.01em | 600 |
| Citation mark | Inter | 0.7em, superscript | 0 | 600 |

Hierarchy comes from face, size and weight together. There is no uppercase anywhere except acronyms.

### 3.4 Space, rules and depth

- **Spacing:** a 4px base: 4, 8, 12, 16, 24, 32, 48, 64, 96, all in `rem` so it scales with the user's text size. Sections are separated by 64px and a hairline. Items within a section by 24–32px.
- **Rules:** 1px `--rule`. They are the main structuring device and replace card borders.
- **Radius:** 4px on inputs, buttons, badges and popovers. 0 on sections. The A4 sheet has 2px.
- **Elevation:** shadows only on things that float: popovers, the export menu and the A4 sheet (`0 1px 2px rgb(0 0 0 / .06), 0 8px 24px rgb(0 0 0 / .08)`). Nothing else has a shadow.
- **Layering:** top nav 20, TOC 10, popovers 30, toasts 40.

## 4. Layout

- **Desktop (≥ 1100px).** A top nav, 56px tall. Under it, two columns:
  - a 220px sticky TOC on the left;
  - the document on the right, with a 72ch prose column. Tables and the pitch sheet can widen to 960px.
- **Tablet (768–1099px).** The TOC becomes a sticky one-line "Contents" control under the nav, which opens a menu.
- **Phone (< 768px).** The same "Contents" control. Tables turn into stacked rows, and the A4 sheet scales to fit the width.
- **Nav, left to right:**
  - the wordmark (a link to home);
  - the command bar, shown only when a report is open;
  - Run details, Export and the theme toggle.

No horizontal page scroll at 320px.

## 5. Components

Each component below replaces one or more existing files. It reuses the logic but not the markup.

1. **Wordmark.** "AI Opportunity Studio" in Newsreader. No icon. (Replaces the logo and sparkle in `App.tsx`.)
2. **Intake (no report open).** A centred column, ~560px wide, with:
   - a serif heading, "Research a company";
   - one large input, plus an optional website input that appears on focus or behind a "Add website" link;
   - Run, and the prototype option as a quiet checkbox;
   - the example companies as an inline list of text links: Adani Realty · Sobha · Prestige …;
   - **Saved reports** underneath, as a plain list: name, date, data quality. One line each, no chips.

   (Replaces `CompanyPicker`, `SavedRuns` and the hero.)
3. **Command bar (report open).** The intake collapses into a single input in the nav: "Research another company…". `/` focuses it, Enter runs, Esc blurs. Saved reports appear as suggestions as you type. It has no open/close animation, because it's keyboard-driven.
4. **Run timeline (during a run).** A vertical list of the 4 stages. Each row shows a status glyph (a ring, a filled dot, or a check) as an inline SVG, the stage name, elapsed time, sources read, tokens and calls. The streamed notes appear under the active stage as monospace log lines, newest last, 13px, `--ink-3`. There are no progress bars or spinners beyond one small dot that pulses for the active stage; with reduced motion it doesn't pulse. (Replaces `RunView`.)
5. **Report header.**
   - The company name in serif and a one-line description.
   - Website · run date as one meta line.
   - Two quiet badges, text on `--tint` with no border: "Medium data quality" and "Verified 9/10 claims".

   (Replaces `ReportHeader`.)
6. **Metrics strip.** 4–5 figures in a row, separated by hairlines. Each shows the figure (tabular), a label, and a superscript citation with its date in the popover, e.g. revenue (FY26), area sold (Q1 FY27), projects, cities, leadership. The figures come only from cited, current facts. If fewer than 3 exist, the strip doesn't render rather than showing blanks.
7. **Table of contents.** In order: Overview, Key information, Challenges, Opportunities, CEO pitch, Sources.
   - Scroll-spy via IntersectionObserver.
   - The active item shows ink colour and a 2px accent bar on the left.
   - Each entry is a link to `#section-id`, so it's keyboard-reachable and deep-linkable.
   - No animation.

   (Replaces `SectionTabs`.)
8. **Section.** An h2 in serif, preceded by its number in `--ink-3` (Inter, tabular), with a hairline above it. No container.
9. **Challenge item.** A numbered list (`1.`, `2.` …) with the title in serif h3, then three labelled rows, **Evidence → Reasoning → Impact**:
   - Evidence: the signals, with citation marks.
   - Reasoning: the causal chain, as prose.
   - Impact.

   Category and severity go in one meta line. Filtering is a row of plain text toggles, kept in `?cat=` as today.
10. **Opportunity table.**
    - Columns: rank, title, then ROI (adjusted), CEO relevance, feasibility, speed and moat, each as a tabular number with a tiny 0–10 bar. Then evidence %, and the weighted score.
    - The recommended row is marked with "Recommended" text in the accent, with no star or colour fill.
    - Clicking a row (or Enter or Space on it) expands it in place, on `--tint`, to show: mechanism, applies to, build vs buy with vendor links, the 30/60/90 pilot, data readiness, compliance, and biggest risk.
    - Ideas that didn't win show their "why not" line, muted, under the title.
    - The sensitivity result is one sentence under the table.
11. **CEO pitch preview.** The real A4 page: the same HTML that the one-page PDF prints (a new `GET …/export/pitch.html` serves the exact template), shown in a sandboxed iframe on `--sheet` with the floating shadow and scaled to fit. It sits beside the Trace panel on wide screens and below it on narrow ones. Because the preview is the export, the two can't drift.
12. **Export menu.** In the nav and in the pitch section:
    - Copy pitch, Print pitch
    - One-page PDF, Full report PDF, Deck (.pptx), Download all
    - Email draft…

    It's a proper menu: arrow keys, Home and End, Esc to close, focus returns to the trigger. The email panel opens as a side sheet on desktop and a full-height sheet on phones.
13. **Run details popover.** Provider, models (main and cheap), tokens and calls per stage in a small table, total time, documents read, and cache hits. (Moves the model id out of the header.)
14. **Citation mark and popover.** As built in Phase 6, restyled: an accent superscript, with a popover on `--sheet` showing title, date, type and the link. It opens on hover after 300ms or instantly on focus. Once one is open, neighbouring popovers open instantly (emil-design-eng's tooltip rule).
15. **Sources.** The final section: a numbered list matching the [n] marks, each entry with title, type, date and link.
16. **Buttons.** Three kinds:
    - **primary:** accent fill, used once per view;
    - **secondary:** a 1px `--rule-strong` outline;
    - **quiet:** text only.

    All are 36px tall, or 44px on touch devices. They respond on press with `scale(0.98)`.
17. **Toast.** Bottom-centre, on `--sheet` with a hairline border. Kept for copy confirmations and errors only.

## 6. Motion

**Default: almost nothing moves.** This is a reading tool used repeatedly, so motion is only for state changes the reader would otherwise miss.

| Element | Animates? | Spec |
|---|---|---|
| Popovers, export menu, citation popover | Yes | Opacity plus `scale(0.98 → 1)` from the trigger's origin. 160ms on enter, 120ms on exit, with `cubic-bezier(0.23, 1, 0.32, 1)` |
| Expanding a table row | Yes | Height via `grid-template-rows: 0fr → 1fr` and content opacity, 180ms ease-out |
| Email side sheet | Yes | Slides from the right and exits to the right, 240ms in and 200ms out, with the drawer curve `cubic-bezier(0.32, 0.72, 0, 1)` |
| Button press | Yes | `scale(0.98)`, 120ms |
| A new run log line | Opacity only | 150ms |
| Section entrance staggers, tab fades | **No** | Removed |
| TOC scroll-spy, command bar, keyboard shortcuts | **No** | Never animate keyboard actions |
| Smooth scroll to a section | Yes, unless reduced motion | Native `scroll-behavior: smooth` |

- **Reduced motion:** all transforms are removed and opacity fades capped at 120ms. The active-stage dot doesn't pulse.
- **Gradients, glassmorphism and emoji icons:** none. Icons are a small set of inline SVGs with 1.5px strokes.
- **Library:** I propose **removing `framer-motion`**. The motion above is plain CSS transitions, which saves about 100 KB of JS and fits the "almost nothing moves" rule.

## 7. Accessibility and quality bar

- AA contrast for every text pair. The values in §3 are checked, and the brand accent is clamped to 4.5:1 or better.
- A visible focus ring everywhere: 2px solid `--accent` with a 2px offset. Never removed.
- Landmarks: `header`, `nav[aria-label=Contents]`, `main`, and one h1. Headings never skip levels.
- Keyboard paths:
  - `/` focuses the command bar.
  - The TOC links are tabbable.
  - Table rows expand with Enter and Space.
  - Menus use arrow keys.
  - Esc closes anything that's open, and focus returns to its trigger.
- Hit targets are at least 44px on touch devices.
- Hover effects only apply under `@media (hover: hover) and (pointer: fine)`.
- Respects `prefers-reduced-motion`, `prefers-contrast: more` (`--rule` darkens to `--rule-strong`) and `prefers-color-scheme`.

## 8. What stays from the earlier frontend work

- URL state (`?run=`). `?tab=` becomes `#section`, and old `?tab=` links redirect to the matching anchor.
- The print stylesheet (now just the A4 sheet), lazy-loaded views, and focus management on route change.
- The axe-core audit, Toasts, the theme toggle with no flash on load, and the Phase 6 citations and trace.
- The Phase 8 export endpoints, which the UI only calls.

## 9. Build order (Phase 9, step 2)

1. Tokens, fonts and the base layout. Remove framer-motion.
2. Nav with the wordmark, command bar, Run details and theme toggle. The intake page.
3. Report document: header, metrics strip, TOC with scroll-spy, and the Overview and Key information sections.
4. Challenges, the opportunity table with expanding rows, and Sources.
5. CEO pitch: the `pitch.html` endpoint, the A4 iframe preview, the Trace panel, and the export menu restyle.
6. Run timeline.
7. Review: `break-ui` with worst-case data, then the axe audit, a responsive sweep (320 / 768 / 1100 / 1440) and a keyboard pass. Screenshots go in the README in Phase 10.

## 10. Decisions to confirm

1. **One scrolling page with a TOC instead of tabs.** The brief asks for this. It makes the report read like a document and print sensibly.
2. **Self-hosted Newsreader and Inter**, rather than Google Fonts.
3. **Remove framer-motion** in favour of CSS transitions.
4. **The pitch preview is the real export HTML** in an iframe, rather than a React re-creation of it.
