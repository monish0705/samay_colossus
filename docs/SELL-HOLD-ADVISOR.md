# Sell-or-hold integration

## Daily-date comparison and projected later proceeds

The advisor compares every saved forecast date inside the verified holding limit,
plus the explicitly selected planning date. The 10,000-plan safety limit still
applies; increase the quantity increment or disable multi-date comparison for
large searches. Previously the form considered only 1/3/7 days and one selected
date, so it could miss a different model-supported selling date.

The response now includes `decision_support.best_holding_plan`: the feasible
holding plan with highest central total net proceeds, independent of risk choice.
The UI shows its held quantity, immediate-sale quantity, target date and saved
forecast, projected later net proceeds, incremental gain/loss against selling
everything now, and adverse loss. A conservative risk objective can still select
immediate sale while this comparison exposes the projected alternative. Projected
gain is not total farm profit: production costs were not supplied.

Live checks against all 60 saved Copra dates produced hold-all, partial-hold and
sell-now outcomes. These used **EXAMPLE_ONLY** farmer quotes/costs and a future
realization factor of 1, not actual executed sales. With 20 quintals, assumed
today quote INR 15,000/quintal, zero immediate cash, 20 quintals storage, explicit
costs/loss and balanced risk, the selected scenario held 20 for two days with
INR 66,088.71 central incremental proceeds. The saved future mandi point was
INR 18,500/quintal; this result assumes the farmer actually realizes that price.
It does not establish a model-predicted market rise from today's mandi price.
With INR 10,000 cash and storage for 10 quintals, it sold 10 and held 10. With an
assumed current quote of INR 20,000, it selected full immediate sale instead.
Exact inputs and outputs: `reports/sell-later-live-results.json`.

Zero storage cannot support holding. A last-price baseline is flat by definition;
storage losses/costs can make immediate sale economically preferable. No forecast
is increased artificially to force a profitable hold recommendation.

The advisor now uses the saved prediction service and the existing Decimal
optimizer. Previously, long crop defaults had no model, point forecasts without
calibrated intervals were discarded, and results emphasized only the safe
immediate-sale fallback. The new flow retains that fallback and separately
displays an explicitly conditional plan, with consistent costs, charts and speech.
Hardcoded crop-card reference prices and unsupported year-over-year statistics
were removed; references now come from dated stored observations.

Select a crop, enter harvest and a realistic buyer quote, cash need, actual storage
capacity/costs/loss assumptions and risk preference. Short and longer saved daily
horizons are listed with availability; see [DAILY-HORIZONS](DAILY-HORIZONS.md).
The selected exact date uses its own saved artifact. Beyond saved evidence, enter
a future buyer-price assumption or explicitly choose a flat dated-price scenario.
No missing model is silently converted into a confident holding recommendation.

Net proceeds include commission, market fees, fixed and variable transport,
handling, storage, physical deterioration and quantity-step rounding. Mandatory
cash, storage and market-lot constraints cannot be relaxed. The result includes
today's quantity/cash, later saleable quantity, scenario proceeds, adverse loss,
break-even price, alternatives, exact arithmetic and source/model timestamps.
User future buyer quotes are not discounted a second time by a mandi realization
factor. Unsupported intervals stay absent; reviewed stress percentages are
explicit assumptions, not model confidence bands.

## Dated external context

`scripts/refresh_market_context.py` collects public Open-Meteo city weather through
its documented geocoding/forecast APIs, the LPSC/ISRO Bengaluru 2026 holiday table,
PIB's published RSS directory/feed, and The Hindu BusinessLine agri-business RSS.
Raw responses, URLs, hashes and capture timestamps are archived in `data/context`.
API keys, private farmer locations and personal information are not required.

Weather is a **market-city proxy**, not a farm or warehouse measurement. The source
covers at most 16 days; no weather is invented for the rest of a 90/365-day plan.
Outdoor-storage rain blocking applies only when the user explicitly enables it,
and missing required forecast coverage blocks holding under that rule. Protected
storage is still an assumption, not a verified facility booking.

The office holiday list does not establish mandi closures, demand or price effects.
No 2027 calendar has been invented. The captured PIB feed had no items; published
general agricultural headlines are labeled general context, not direct crop-price
signals. Absence of a matching headline does not mean no relevant news exists.

**No learned numeric weather, festival or news price adjustment is applied.**
Those inputs lack historical as-of validation. They are reviewable evidence and
explicit physical constraints, not fabricated percentage boosts to forecasts.
Historical decisions exclude context captured after the decision. Hash tampering,
future publication times and stale weather/news trigger unavailable/partial flags.

## Actual live checks with illustrative farmer inputs

`scripts/verify_sell_hold.py` sends requests to the running backend. All buyer
quotes/costs are marked EXAMPLE_ONLY; these are not actual sales or profitability
claims. The saved monthly forecast is genuine service output.

| Case | HTTP | Observed action |
|---|---:|---|
| Saved short forecast with cash/storage constraints | 200 | Conditional split |
| Zero storage | 200 | Sell all now |
| Unachievable cash requirement | 409 | Infeasible |
| Falling future buyer-price assumption | 200 | Sell all now |
| High storage charge | 200 | Sell all now |
| Explicit 90-day buyer-price assumption | 200 | Conditional split |
| 90-day outdoor rule with missing weather coverage | 200 | Sell all now |
| Saved 30-day Copra baseline | 200 | Conditional split |
| Unsupported 365-day model | 200 | Insufficient evidence; immediate-sale fallback retained |

The illustrative 20-quintal monthly case sold 10 and held 10; that is a computed
example under its displayed inputs, not a universal recommendation.
Exact requests, monetary outputs and model/source lineage are saved in
`reports/sell-hold-live-verification.json`. Browser checks confirmed equal numbers
in English/Kannada and a reachable language selector on a narrow screen.

Future mandi modal-price uncertainty does not include all quality, bargaining,
buyer, transport or individual realization uncertainty. The farmer makes the final
decision; no statistical forecast is a guaranteed selling price.
