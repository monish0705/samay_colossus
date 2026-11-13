# SAMAY: project gaps and AI build prompts

Prepared 4 November 2026 from the repository and the attached UI screenshots. Use the three prompts in order with a coding model that can read and edit this repository. Prompt 1 audits and plans; Prompt 2 implements; Prompt 3 prepares and verifies the judge demo.

## What is already working

- SAMAY already has a FastAPI backend, React/TypeScript frontend, SQLite persistence, bilingual support, market history, source lineage, and a cash-aware selling optimizer.
- The repository contains 1,943 imported AGMARKNET records for Kolar tomato series through 31 October 2026. The latest record shown in the screenshots is dated 31 October and was fetched on 4 November; that is historical market reporting, not a live price feed.
- Research-only chronological comparisons and held-out errors are documented in `docs/MODEL-RESULTS.md`. The current champions are simple baselines. A 3-day Local-grade rolling-mean result underperformed the naive baseline on its final test.
- The screenshots correctly disclose that no operational forecast is deployed. The optimizer must not turn those research artifacts into a live forecast or a confident hold recommendation.
- The UI has a polished visual foundation, English/Kannada support, a five-step advisor, scenario exploration, and an evidence/transparency view. Preserve these strengths.

## Priority corrections

### P0 — Make the farmer's first decision easy

The advisor is currently an assumptions-heavy form. The farmer is asked to supply today's buyer quote, fees, cost assumptions, storage conditions, a loss rate, and a source note; the final review screenshot has blank values and an error. This makes the product look unfinished and asks a farmer to understand too many details before seeing value.

- Start with a short, large-text flow: crop/market (preselected and clearly scoped), harvest quantity, cash needed today, storage available (yes/no and capacity), and an optional buyer quote.
- Prefill the latest official modal price as a clearly dated *market reference*, never as a guaranteed farmer price. Let the farmer replace it with their buyer's quote.
- Put fees, transport, storage cost, loss assumptions, holding days, and risk preference under a clearly labeled “More details” section with plain-language defaults only where justified.
- Keep zero/blank values distinct. Validate each step before advancing; explain errors next to the field and never show an empty review as a valid plan.
- Explain the recommendation in Kannada/English using familiar words, large touch targets, readable numbers, and a clear next action. Keep model terms in Judge Mode.

### P0 — Make the recommendation workflow truthful and complete

The core calculation is a strength, but recommendations can only be as useful as the price input and assumptions. The live-forecast page says “Not deployed,” and the screenshots show the farmer has to provide today's quote. A farmer selling decision needs dated reference data, costs, a cash constraint, storage feasibility, a downside comparison, and a clear confidence state on one results screen.

- Show source, report date, age of report, market, crop, variety/grade, and units beside every reference price.
- Compare sell-all-now, cash-first split, and conservative split using the backend optimizer. Display immediate *net* cash, later net proceeds, total proceeds by scenario, costs, held quantity, break-even future price, and feasibility.
- If an operational forecast is unavailable or stale, say so prominently. Do not invent future prices or recommend holding on a fictional central estimate. Offer an explicitly user-controlled downside/base/upside scenario simulator and/or a sell-now calculation; label it “scenario only.”
- The recommendation should explain why the plan wins, what could change it, and when selling everything now is the safer feasible option. Any changed input must cause a backend recalculation before the result is called current.
- Preserve infeasible cash needs as infeasible; do not silently relax cash, storage, market-lot, loss, or cost constraints.

### P1 — Build evidence-led forecasting rather than a “world factors” black box

The request for current price, old prices, same time last year, festivals, and world events is directionally right, but the app does not yet have those joined, point-in-time features. Adding feature names or an LLM explanation does not make a forecast reliable. The existing study shows the naive baseline can beat more complex models, and the research models are not deployed.

- Add same-market/same-crop historical comparisons (including a year-over-year seasonal view) only when the series is sufficiently comparable. Distinguish actual observations from forecasts and preserve gaps.
- Treat arrivals, weather/monsoon, fuel, export/import policy, international prices, exchange rates, major events, and festivals as candidate features only when a relevant, licensed/reliable source, timestamp, coverage, and point-in-time availability can be established.
- Do not use future revisions, later-published records, or current values as if they were known at an earlier forecast date. Do not fill missing market days with made-up values.
- Test added features against naive persistence and rolling benchmarks on identical chronological folds and an untouched final test. Report MAE in INR/quintal, WAPE or sMAPE, sample sizes, interval coverage/width, and performance by horizon. Promote a more complex model only if it improves out of sample under a predeclared rule.
- If evidence is inadequate, retain the baseline or disable the forecast and explain why. This honest fallback is part of the product, not a demo failure.

### P1 — Separate farmer UX from judge evidence

The screenshots mix a friendly farmer workspace with numerous technical navigation items. Keep the uncluttered design language, but add a clear Farmer Mode / Judge Mode distinction. Farmers should not need to navigate model transparency to get a plan; judges should be able to inspect provenance, data freshness, model status, evaluation, optimizer assumptions, and reproducible calculations.

### P1 — Finish the demo path and responsive states

The dashboard and charts look polished, but the captured advisor review is empty, forecast cards are unavailable, and some screens leave the user without a satisfying next step. Ensure first-run, disconnected, stale-data, no-forecast, invalid-input, calculation-error, infeasible-cash, and successful-plan states are deliberate and understandable. Demo examples must be labeled illustrative and must call the real backend for arithmetic.

## Prompt 1 — Audit this repository and produce an implementation plan

```text
You are the senior product engineer for SAMAY, a farmer-first harvest selling decision product. Work in the existing repository; inspect it before proposing changes. Read README.md, AGENTS.md if present, docs/STATUS.md, docs/MODEL-RESULTS.md, docs/JUDGES.md, docs/DEMO.md, the frontend advisor/results/market pages, and the FastAPI selling/forecast/readiness services. Inspect the attached screenshots as current UI evidence.

Product goal: help a smallholder farmer decide how much tomato harvest to sell now and how much, if any, to hold, while meeting today's net cash need and respecting actual costs and storage limits. Pilot scope is Karnataka → Kolar → Kolar APMC → tomato. The app should have a simple Farmer Mode and an evidence-rich Judge Mode.

Important current facts to verify from the repository rather than assume: 1,943 official AGMARKNET observations span multiple distinct series through 31 Oct 2026; research artifacts are retrospective and are not deployed; live forecast availability may be false; the optimizer already handles cash, costs, storage, and risk constraints. Preserve existing working architecture and the source/evidence safeguards. Do not rewrite the project or claim it is broken just because a responsible readiness gate is closed.

Deliver an audit, not code changes in this phase. Give me:
1. What works today, with exact file paths and evidence.
2. A prioritized P0/P1/P2 defect list. For each issue, state its user impact, the likely files/services involved, and a concrete acceptance criterion.
3. A proposed end-to-end farmer flow and separate judge demo flow.
4. A data/model plan for current market price, historical trend, same-period-last-year comparison, festivals/seasonality, and relevant world/national drivers. For each candidate feature, state what source, publication timestamp, market/crop relevance, and minimum evidence is required. If unavailable, explicitly mark it unavailable; never suggest fabricated data.
5. A list of likely regression risks and existing tests/checks that cover the affected areas.
6. A small implementation sequence that can be completed incrementally in this repository.

Rules: inspect before recommending; distinguish verified facts from inference; don't invent APIs, sources, prices, forecasts, performance, or farmer outcomes; don't promote a research-only artifact to production; don't add an LLM as the financial calculator. Prioritize a simple and usable farmer flow over adding pages. Stop after the audit and plan so the human can review it.
```

## Prompt 2 — Implement the farmer-first decision workflow

```text
Implement the approved SAMAY audit plan in this existing repository. First inspect the current working tree and relevant instructions; preserve unrelated user work. Keep the existing FastAPI + React/TypeScript architecture and reuse tested domain services. Make small, coherent changes; do not replace the project with a generic template.

PRODUCT
SAMAY helps a farmer decide how much of a harvest to sell now to meet immediate net cash needs and whether holding any remainder is feasible and worthwhile. Initial validated scope: Karnataka, Kolar APMC, tomato, quintals, INR. Provide two experiences: Farmer Mode (simple, bilingual, mobile-first) and Judge Mode (provenance, freshness, model evidence, evaluation, assumptions, and calculation detail).

FARMER FLOW
1. Start with one clear action: “Plan my sale.” Preselect the supported market/crop and state this scope plainly; do not offer unsupported crops as if they work.
2. Ask one small group of questions at a time: harvest quantity; cash needed today; whether storage is available and its capacity; optionally the farmer's buyer quote. Show the latest official modal price only as a dated wholesale reference and allow a farmer quote to override it. Never call modal price the farmer's guaranteed sale price.
3. Put detailed transport, commission/fees, handling, storage costs, holding duration, and loss assumptions in an optional “More details” section. Use only documented defaults. If an assumption is required but unknown, ask in plain language; do not silently invent an agronomic loss rate.
4. Validate before advancing. Empty, malformed, negative, out-of-range, or contradictory inputs must get a nearby plain-language error. The review step must show the actual values and cannot submit an empty plan.
5. Call the real backend optimizer. Compare sell-all-now, cash-first, and conservative split plans when feasible. Results must show immediate net cash, held quantity, costs, later proceeds, total net proceeds, downside/base/upside outcomes where supported, break-even future price, and why the recommendation was selected. Show an explicit infeasible state when today's cash need cannot be met.
6. If no operational forecast exists or data is stale, do not create a made-up predicted price or a confident hold recommendation. Provide a clearly labeled scenario-only simulator with farmer/judge-controlled future price assumptions, and show a dated sell-now estimate. Recalculate through the backend on every change; mark old results stale until recalculated.
7. Explain the result in simple English and Kannada. Use readable typography, larger controls, uncluttered navigation, keyboard and mobile support. Keep technical model terms in Judge Mode.

EVIDENCE AND MODEL RULES
- Preserve official source provenance, actual report/fetch dates, units, grade/variety distinctions, missing dates, and stale-data warnings.
- Keep actual historical points visually distinct from forecasts and scenarios.
- Existing 1,943-record retrospective studies are research only. Do not deploy or relabel their artifacts as live forecasts. Do not call WAPE-derived values “accuracy.”
- Treat last-year comparisons, festivals, arrivals, weather, fuel, exports/imports, currency, international prices, and world events as candidate inputs only after verifying a relevant source and point-in-time availability. Never let an LLM invent a feature value or turn a news headline into an unvalidated price adjustment.
- Compare forecasting candidates with naive persistence and rolling baselines on identical chronological validation data; hold the final test untouched. Promote a complex model only under an explicit out-of-sample improvement rule. If data is inadequate, report low confidence or no forecast.
- Financial arithmetic and plan ranking belong in deterministic backend code, not an LLM.

IMPLEMENTATION EXPECTATIONS
- Inspect current APIs, schemas, and UI before editing. Extend them compatibly where possible.
- Keep all three views consistent: dashboard/source date, advisor inputs, and result market series.
- Make source/date/confidence visible at the point the farmer sees the price or recommendation.
- Preserve the readable green visual style in the supplied screenshots, but simplify the farmer experience and improve narrow-screen layout.
- Add or update focused automated checks for any changed calculation, validation, or UI behavior. Run the repository's relevant checks and report exact results; distinguish a failing readiness gate caused by unavailable authentic operational forecast evidence from an implementation/test failure.
- Update the appropriate docs and the demo walkthrough after behavior changes.

Before finishing, summarize the files changed, user-visible behavior, data/model limitations, commands run and outcomes, and any remaining blocker. Do not claim “hackathon ready” unless the end-to-end demo actually works.
```

## Prompt 3 — Make the demo judge-ready and verify the complete path

```text
Now prepare SAMAY for a live hackathon judging demonstration using the current repository state. Inspect the implementation and docs first. Fix remaining user-visible defects that block a reliable, understandable demo; do not add unsupported claims or unrelated features.

DEMO STORY (about 3 minutes)
1. Open the dashboard and explain what SAMAY does in one sentence. Point to the exact market report date, official source, and reporting freshness.
2. In Farmer Mode, enter a realistic, explicitly illustrative harvest, cash need, buyer quote (or dated market reference), storage capacity, and a small set of costs. The demo values must be labeled illustrative, not live farmer outcomes.
3. Calculate via the real backend. Show the immediate net cash requirement, sell-now / split comparison, held quantity, costs, downside and break-even in plain language. Change one input and recalculate to prove the plan changes or explain why it does not.
4. Show an unavailable/stale-forecast case honestly. Demonstrate scenario-only price sensitivity without presenting it as a prediction.
5. Switch to Judge Mode and show source lineage, observed history, what model is or is not deployed, actual chronological evaluation metrics and sample sizes, optimizer rules, and known limitations.
6. Switch English/Kannada and show the same underlying result, then show a narrow/mobile layout.

RELIABILITY REQUIREMENTS
- Every route has a meaningful loading, empty, disconnected, stale, invalid, error, and success state where relevant.
- No screen displays placeholder zeros, blank review values, stale results presented as current, or dead-end buttons.
- The demo remains usable without relying on a third-party live API during judging. Use only bundled, provenance-preserving authentic observations for history; label illustrative user inputs and scenario prices. Do not forge “live” data or backdate fetches.
- Accessibility basics: keyboard operation, visible focus, labels, useful validation, contrast, and large touch targets.
- Check that observed, predicted, and scenario values are visibly distinct and that all INR/quintal/date labels agree.
- Keep Judge Mode detailed without burdening Farmer Mode.

Run the existing relevant backend/frontend tests, type checking, lint/build, and the repository release/readiness commands available for this project. Fix regressions caused by your changes. Report exact commands and outcomes, including authentic readiness blockers. Do not weaken tests, hide warnings, edit historical evidence to improve metrics, or claim profit uplift/forecast accuracy without support.

Finish with: (a) a concise demo script with click-by-click actions and spoken narration; (b) the exact illustrative inputs and backend-calculated expected result; (c) changed files; (d) verification outcomes; and (e) honest remaining limitations. If a dependable forecast cannot be validated, make the strongest judge story the cash-aware optimizer, real source evidence, transparent uncertainty, and correct no-forecast fallback.
```

## Suggested use

Give Prompt 1 to the coding model and review its audit. Then give Prompt 2 with the approved priorities. After implementation, use Prompt 3 to polish and rehearse the full path. Paste the prompts separately so the model does not skip the inspection phase or blur research evidence with operational behavior.
