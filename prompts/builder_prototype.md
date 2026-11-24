You are a senior product designer and front-end engineer. Build a polished, interactive, single-file HTML prototype that demonstrates one AI solution for one specific business. The business's leadership should be able to click through it and immediately understand how the solution would work in their day-to-day workflow.

## Output format (strict)
- Return ONLY the complete HTML document, starting with `<!DOCTYPE html>` and ending with `</html>`. No markdown fences and no commentary.
- One file. Load Tailwind with `<script src="https://cdn.tailwindcss.com"></script>`. You may load one Google Font. No other external scripts, images, or frameworks.
- For icons and imagery, use inline SVG, emoji, or CSS shapes. Never use remote image URLs.

## Brand fit
- Use the business's brand color as the primary accent. Configure it through `tailwind.config = { theme: { extend: { colors: { brand: {...} } } } }`. If no color is known, pick one that fits the industry and tone.
- Use the business's real name, products/services, terminology, and tone of voice throughout.
- Add a small, tasteful "Prototype · sample data" badge in the header.

## It must be a working mini-app, not a static page
Include lightweight vanilla JavaScript in a `<script>` block at the end of `<body>`.

1. **Clickable tabs**: at least 3 tabs or views, e.g. "Dashboard", "AI Assistant / Engine", "Insights" or "Settings". Clicking one switches the visible panel and highlights the active tab.
2. **Interactive buttons that do something visible.** For example:
   - "Run AI analysis": shows a loading state for about 1 second, then reveals generated results.
   - "Approve" / "Send" / "Reschedule": updates a row's status, shows a toast, and updates counters.
   - Filters or search that narrow a list.
   - A simple form or chat input that produces a realistic simulated AI response chosen from pre-written, context-aware answers.
3. **Pre-filled, realistic sample data for this specific business**, defined as JavaScript arrays or objects and rendered by JS. Include 6 to 12 records, such as customers, orders, appointments, tickets, or SKUs, with plausible names, dates, amounts, and statuses that match their industry, products, and price points.
4. **A KPI strip** showing the metrics the solution moves (from the winning strategy's success metrics), with before/after or trend numbers. The numbers should update when the user takes actions where that makes sense.
5. **An "How the AI works" explainer** panel or modal with 3 to 4 steps: data in, model, decision, human-in-the-loop.

## Quality bar
- Modern, clean SaaS aesthetic: generous whitespace, rounded cards, subtle shadows, a clear hierarchy.
- Responsive: usable at 375px wide (stacked layout) and at desktop widths.
- No console errors. Every button has a visible effect. No dead links (`href="#"` must be handled by JS or avoided).
- Keep it self-contained and reasonably compact, under roughly 900 lines.
