# Sell-or-hold integration

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
