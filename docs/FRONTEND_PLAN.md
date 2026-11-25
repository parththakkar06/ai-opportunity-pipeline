> **Superseded (Nov 25, 2026):** this plan describes the first frontend (tabs, slate/sky palette, framer-motion). The interface was redesigned in Phase 9 of the assessment upgrade; see `docs/DESIGN_DIRECTION.md` for the current design. Kept for history.

# Frontend redesign plan: AI Opportunity Studio

> **Status (Nov 25, 2026): all 6 phases done.**
> - **Phase 1:** design tokens, light and dark theme, typography, focus, URL state.
> - **Phase 2:** shell and intake: picker, saved runs with Resume, toasts, mobile sheet.
> - **Phase 3:** live run view, plus demo mode (`scripts/demo_api.py`).
> - **Phase 4:** report redesign.
> - **Phase 5:** one-page print and PDF output for the pitch.
> - **Phase 6:** QA.
>
> **Phase 6 results:**
> - **axe-core 4.14 (WCAG 2.2 AA + best practice):** 0 violations on all 5 report tabs in light and dark, the start screen, and the mobile sheet.
> - **No horizontal scroll** at 375, 768, 1024 and 1440px on every tab.
> - **Keyboard-only path works:** skip link → saved report → title → Copy pitch.
> - **Initial JS:** 445.5 KB (139.3 KB gzipped) → 259.5 KB (82.9 KB gzipped), via `LazyMotion` and lazily loaded report and run views.
> - **Reduced motion:** checked by code review. The pane can't emulate the OS setting.
**Status:** plan only, nothing implemented yet. `framer-motion@14.14.0` is installed in `frontend/`.
**Sources:**
- The UI/UX Pro Max skill. The design system is saved in `design-system/ai-opportunity-studio/` (`MASTER.md`, `tokens.css`, `tokens.json`), and the skill also supplied targeted UX guideline searches.
- Where the skill's database had **no match**, notably React and framer-motion animation, the recommendation is marked **(fallback: my recommendation)**.

---

## 1. Goal

An executive should be able to:
1. **Pick a company** and see live progress they trust.
2. **Read the 5-section assessment** like a polished consulting deliverable.
3. **Copy, download, or print the one-page CEO pitch**, ready to send.

The interface should look calm, credible, and fast. It should not look like a demo.

---

## 2. Audit of the current UI

These are measured counts from `frontend/src`.

| Finding | Count | Rule it breaks (skill) | Fix |
|---|---|---|---|
| Body copy at `text-sm` (14px) | 49 | Readable font size: 16px minimum for body | Body becomes `text-base`; `text-sm` is kept only for meta |
| `text-xs` (12px) | 25 | Same rule | Use only for labels and badges, never for sentences |
| Text smaller than 12px (`text-[10px]`/`[11px]`) | 2 | Same rule | Remove |
| `text-slate-400` on white (about 2.6:1) | 14 | Contrast of 4.5:1 minimum | Use a `muted-foreground` token at about 7:1 |
| `focus-visible` styles | only 2 | Visible focus states for keyboard users | 3px focus ring on every interactive element |
| Dark mode | none | Style supports both modes | Add a token-based dark theme |
| `aria-live` regions | none | Progress indicators and feedback | Announce stage changes and "Copied" |
| Reduced-motion handling | none | Reduced motion (High severity) | Add `MotionConfig reducedMotion="user"` plus a CSS fallback |
| Small pill buttons (about 28px tall) | 2 groups | Touch targets of 44×44 | Quick-select chips at least 44px tall |
| Indigo `brand-*` accent | 41 refs | Anti-pattern: "AI purple/pink gradients" | Navy and slate, with one blue accent |
| URL reflects state | no | Deep linking (state in the URL) | `?run=sobha&tab=challenges` |
| Long paragraphs fill the full width | yes | Line length of 65–75 characters | `max-w-prose` on narrative text |

Also observed when using the app:
- On mobile, a loaded report renders *below* the control panel, so the user doesn't notice it opened.
- The tab bar has `role="tab"` but no arrow-key navigation.

---

## 3. Design direction (from the skill's design system)

- **Pattern: Trust & Authority.** Credibility first, with a single clear primary action.
- **Style: Accessible & Ethical.** High contrast, 16px+ body text, semantic markup, visible focus, reduced motion respected.
- **Dials:** motion 5/10 (standard) and density 6/10 (standard, slightly dense for the report).

**Color tokens.** These are from `tokens.css`. Components never use raw hex values.

| Token | Light | Use |
|---|---|---|
| `--color-primary` | `#0F172A` (navy) | Headings, the active tab, primary surfaces |
| `--color-accent` | `#0369A1` (trust blue) | **The only** CTA and accent color: Run analysis, links, active stage |
| `--color-background` | `#F8FAFC` | App background |
| `--color-card` | `#FFFFFF` | Cards |
| `--color-muted` / `--color-muted-foreground` | `#E8ECF1` / `#475569` | Secondary surfaces and text (replaces slate-400) |
| `--color-border` | `#E2E8F0` | Dividers |
| `--color-destructive` | `#DC2626` | Errors only |

- **Dark theme (fallback: my recommendation):** the skill marked dark as supported but returned only light values. Mirror the tokens using slate-950 background, slate-900 cards, slate-50 text and sky-400 accent, then check every pair for 4.5:1.
- **Status colors:** severity and data quality use red, amber and green, but **always paired with an icon and a text label**, never color alone.
- **Typography:** Plus Jakarta Sans at 400, 600, 700 and 800, replacing Inter.
  - Scale: 12 for labels, 14 for meta, **16 for body**, 18 for lead text, 20, 24, 30 and 36 for headings.
  - Line height 1.5 for body, 1.2 for headings.
  - Tabular figures (`tabular-nums`) for scores, money and timings.

---

## 4. Information architecture & layout

```
┌───────────────────────────────────────────────────────────────┐
│ Top bar: logo · provider/model status pill · theme toggle      │
├──────────────┬────────────────────────────────────────────────┤
│ Left rail    │ Workspace                                      │
│ (sticky)     │  ▸ Empty state  → "What you'll get" (5 sections)│
│ New analysis │  ▸ Running      → Live run view                 │
│ Saved reports│  ▸ Report       → Report header + 5 tabs        │
│ Run tracker  │                                                │
└──────────────┴────────────────────────────────────────────────┘
```

- **URL state, with no router dependency.** Use the history API with `?run=<slug>&tab=<overview|key-info|challenges|opportunities|pitch>`. Back and forward work, and a report link can be shared.
- **Mobile, below 1024px:**
  - The left rail becomes a collapsible "New analysis" sheet.
  - Opening a report scrolls to the report and moves focus to its `<h1>`.
  - The tab bar becomes a horizontally scrollable segmented control and stays sticky under the top bar.
- **Report header.** It stays sticky in a compact form after scrolling and contains:
  - the company name, industry, and a data-quality badge with an icon
  - the "generated" time
  - the actions **Copy pitch**, **Download .md**, **Print / PDF**, and Prototype when available
- **Live run view.** The workspace shows a large version of the tracker:
  - elapsed time per stage
  - the latest note
  - the model in use, which updates when a fallback switch happens
  - **Stop**
  - after an error, **Resume from stage N**

---

## 5. Components to build or rework

| Component | Change |
|---|---|
| `AppShell` | Top bar, sticky left rail, skip link ("Skip to report"), theme toggle |
| `CompanyPicker` | Quick-select chips at ≥44px with company initials avatars; name and URL fields with visible labels and inline validation; prototype toggle with helper text |
| `SavedRuns` | Searchable list with status icon, data quality and relative date; a "partial" run shows "Resume" |
| `StageTracker` | Vertical stepper with an animated connector, elapsed timer, `aria-live="polite"` announcements, and the model-switch notes |
| `ReportHeader` | Sticky and compact on scroll; action group |
| `SectionTabs` | Arrow-key, Home and End navigation (WAI-ARIA tabs); animated active indicator; synced with the URL |
| `OverviewSection` | KPI strip for scale (revenue, portfolio, employees) as stat cards; geography chips; "what they do" lead paragraph at `max-w-prose` |
| `KeyInfoSection` | Projects table that turns into stacked cards on mobile; timeline for recent developments; public info grouped by category |
| `ChallengesSection` | Filter by category (Operational / Sales / CX); severity shown with icon and label; the **Reasoning** block as the visual hero of each card; signals as a small list |
| `OpportunitiesSection` | Ranked list; "Recommended" card emphasized; score bar showing the 4 rubric criteria (bar + number, not color alone); "Solves ch-x" chips that jump to that challenge |
| `CeoPitchView` | A4-like page with print stylesheet; a/b/c sections; ROI callout; Copy / Download / Print |
| `Toast` | "Copied", "Saved", errors, with `role="status"` |
| `Skeletons` | For report loading, with the space reserved so the layout doesn't jump (CLS < 0.1) |

---

## 6. Motion spec (framer-motion)

The skill's database had no React or framer-motion match, so the APIs below are **(fallback: my recommendation)**. The timing rules come from the skill: one shared set of timings, exits shorter than entries, at most 1–2 animated elements per view, and reduced motion respected.

**Global rules**
- Wrap the app in `<MotionConfig reducedMotion="user">`. Under reduced motion, transforms are skipped and only opacity fades remain.
- Timing tokens:
  - `fast` 150ms for hovers and presses
  - `base` 240ms for tab content and cards
  - `slow` 400ms for page-level changes
- Exits use about 65% of the entry duration.
- Easing: decelerate on enter, accelerate on exit. Springs (`stiffness 400, damping 32`) for indicators only.
- Animate only `opacity` and `transform`, never width or height.

**Where motion is used, one job per spot**

| Spot | Motion | Why |
|---|---|---|
| Active tab indicator | `layoutId="tab-indicator"` spring slide | Shows where you moved to |
| Tab content | `AnimatePresence mode="wait"`: fade plus 8px rise in, fade out | Content change is noticed without distraction |
| Stage tracker | Connector line fills as each stage completes; the active dot pulses gently (paused under reduced motion) | Signals progress |
| Report open | Report header fades in, then sections stagger in by 40ms on **first** load only | One entrance moment |
| Recommended opportunity | One-time highlight ring when the tab opens | Draws the eye to the decision |
| Copy button | Icon morphs from copy to check | Confirms the action |

**Not animated:** data tables, scores, long text, anything on scroll after the first entrance, and looping decorations.

- Avoid `back.out` overshoot on informational UI. The skill flags overshoot on data as reading "sloppy".
- If someone clicks through tabs rapidly, the previous animation is replaced, never queued.

---

## 7. Accessibility checklist

- Text contrast of at least 4.5:1, and 3:1 for UI borders and icons, in both themes.
- 3px `focus-visible` ring on every interactive element, never removed.
- Skip link. Exactly one `<h1>` per view. Headings in order. Real `<button>` and `<a>` elements.
- Tabs follow the WAI-ARIA tabs pattern (roving `tabindex`, arrows, Home and End).
- `aria-live="polite"` for stage changes; `role="alert"` for errors; `role="status"` for toasts.
- Icon-only buttons get `aria-label`; decorative icons get `aria-hidden`.
- Never use color as the only signal: severity, data quality and stage state always have an icon or text.
- Touch targets of at least 44×44, with at least 8px between them.
- `prefers-reduced-motion` and `prefers-color-scheme` are both respected, and the theme toggle overrides the system setting.

---

## 8. Performance

- Lazy-load the report sections and the prototype iframe.
- Load Plus Jakarta Sans with `display=swap` and only the weights used.
- Reserve space with skeletons so the layout doesn't jump.
- framer-motion: import only `motion`, `AnimatePresence`, `MotionConfig` and `LayoutGroup`. Consider `LazyMotion` with `domAnimation` to keep the bundle small.
- Memoize long lists (opportunities, challenges). Keep stream event handling light.

---

## 9. Print and PDF for the CEO pitch

- An `@media print` stylesheet that hides the app shell, sets A4 margins, uses black text on white, and keeps sections from breaking across pages.
- **Print / PDF** calls `window.print()` with the pitch view active.

---

## 10. Implementation phases

| Phase | Scope | Files |
|---|---|---|
| **1. Foundation** | Import tokens into Tailwind v4 `@theme` (light + dark); Plus Jakarta Sans; type scale; `MotionConfig`; theme toggle; URL state hook | `index.css`, `index.html`, `src/lib/useUrlState.ts`, `src/lib/motion.ts` |
| **2. Shell & intake** | `AppShell`, `CompanyPicker`, `SavedRuns`, mobile sheet, skip link, toasts | `components/shell/*`, `components/intake/*` |
| **3. Live run** | Large `StageTracker` in the workspace, elapsed timers, live announcements, model-switch notes, Stop and Resume | `components/run/*`, `App.tsx` |
| **4. Report** | `ReportHeader`, accessible `SectionTabs` with motion, the 5 reworked sections, skeletons, cross-links from opportunities to challenges | `components/report/*` |
| **5. Pitch & print** | A4 pitch view, print stylesheet, Copy / Download / Print | `components/report/CeoPitchView.tsx`, `index.css` |
| **6. QA** | Pre-delivery checklist; checks at 375 / 768 / 1024 / 1440; keyboard-only pass; reduced-motion pass; dark-mode contrast pass; `npm run build`; Python tests | none |

---

## 11. Done means (pre-delivery checklist from the skill)

- [ ] No emoji used as icons; consistent SVG icon set
- [ ] `cursor-pointer` and hover transitions (150–300ms) on clickables
- [ ] Text contrast of at least 4.5:1 in light **and** dark
- [ ] Visible focus states everywhere; full keyboard path from company choice to copying the pitch
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive at 375, 768, 1024 and 1440 with no horizontal scroll
- [ ] Body text at least 16px; narrative text at most about 75 characters wide
- [ ] URL deep links restore the run and tab
- [ ] Builds cleanly (`npm run build`); all Python tests still pass
