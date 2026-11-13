# Cash-aware and risk-aware selling engine — Prompt 6

`app.selling.optimize_selling(request)` is a pure Python function: no database,
network, current clock, model fitting or randomness. It returns Decimal-valued
calculations and an auditable grid comparison. `SellingRequest` strictly validates
named units, scopes, times, schedules and bounded numeric inputs. No live forecast
or agronomic recommendation is invented by this engine.

## Run the explicit example

PowerShell from repository root:

```powershell
.\.venv\Scripts\python.exe scripts/optimize_selling.py --input docs/examples/selling-example.json --output reports/selling-example.json
.\.venv\Scripts\python.exe -m pytest tests/test_selling.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
```

The example is 20 quintals of tomato with a required INR 10,000 immediate net cash.
The price, transaction charges, three-day storage limit and daily loss schedule
are **illustrative configurable assumptions**, not observed government prices,
verified shelf life or a fixed recommendation. Future prices are explicitly
`scenario only`, so the output selects the safe today-only alternative:

```json
{
  "status": "sell_all_now",
  "recommendation_basis": "today_only_safe_fallback",
  "cash_requirement_achievable_on_grid": true,
  "sell_today_quintals": "20",
  "hold_quintals": "0",
  "cash_today_inr": "18700.00",
  "feasible_grid_plans": 9
}
```

Here gross INR 20,000 less INR 1,000 commission and INR 300 transport nets INR
18,700. A test-only validated-price case with otherwise similar inputs permits
partial holding: 11 quintals today nets INR 10,240, while 10 quintals nets less than
INR 10,000. That verifies the algorithm, not an actual forecast or farmer instruction.
The full example output retains hypothetical holding plans, their adverse outcomes
and assumptions, but does not promote them as reliable recommendations.

CLI exit 0 means a constraint-feasible selected plan, 2 means no validated selected
plan, and 1 means invalid input/I/O. Always inspect status and recommendation_basis.
The JSON output represents Decimals as strings, preserving paise. reports/ is ignored
by Git. No extra dependency is needed beyond the existing Pydantic backend stack.

## Input contract and units

Use SellingRequest or a matching dictionary. Unknown fields are rejected. All
money amounts are INR, prices INR per quintal, quantities quintals. Quantity inputs
have at most three decimal places; money/price inputs at most four, with monetary
settlement rounded to paise. Rates are explicit fractions from 0 to 1, never percent
numbers such as 5 for 5%. NaN/infinity, negative prices/costs/quantity, naive
timestamps and boolean holding durations are rejected. Total quantity must be positive.

Required fields cover scope (commodity, market, variety, optional grade), aware
decision_at, total quantity, today's realistic farmer selling price and its source/
assumption, immediate required net cash, storage capacity, decision increment,
market quantity step, minimum sale lot, maximum horizon, crop-specific storage
profile, today's SaleCosts, risk tolerance, and zero or more HoldingOptions.

CropStorageProfile explicitly supplies matching commodity, maximum holding days,
storage conditions and assumption source. HoldingOption supplies days, one loss
fraction and one storage rate for **every day**, optional fixed storage cost,
payment timing, future transaction costs and assumption notes. Repeating one daily
rate is supported by repeating it in the schedule; period-specific assumptions
use different rates for each day in the applicable period. There is no universal
tomato spoilage rate or automatic cold-storage shelf-life assumption.

All holding durations must be unique. Durations exceeding either the supplied
crop holding limit or maximum allowed horizon are rejected from the search with
a counted reason. Crop limits are input constraints, not independently verified
agronomic facts: the caller must obtain appropriate local evidence for variety,
ripeness, weather and actual storage conditions.

## Net cash and transaction cost accounting

For each nonzero sale:

1. Gross = quantity × gross farmer selling price, rounded to paise HALF_UP.
2. Combined percentage charges = gross × (market fee rate + commission rate),
   rounded once. Their combined rate must be <1. Commission is allocated rounded
   to paise and the remaining percentage charge to the market-fee line, so the
   ledger reconciles without double-rounding the subtotal.
3. Subtract fixed transport + variable transport per sold quintal, variable handling
   per sold quintal, and fixed transaction/market charge. Fixed costs apply only
   when quantity sold is nonzero. Separate today and later sales incur separate
   fixed charges; future charges can differ from today's quotation.
4. Net sale proceeds = gross less all those costs. Negative returns remain negative,
   never silently clipped to zero or hidden from the comparison.

Tomorrow's modal price is not simply substituted for a farmer's transaction price.
The input today_price must be a realistic expected **gross transaction price**;
all listed charges are then deducted. Costs already netted into a quote must not
be deducted a second time. The caller must describe the quote/cost basis.

Storage is charged on each day's **opening physical quantity** before that day's
loss; each daily amount and the fixed storage charge are rounded to paise. If
payment is today, the full holding cost is deducted from cash today. Otherwise it
is deducted from later net proceeds. This deliberately requires specifying who
pays when: no borrowing, credit or external initial cash balance is assumed.

Immediate cash = today's net sale proceeds minus upfront storage charges. It must
meet the mandatory cash requirement exactly after settlement rounding. Unrealized
later proceeds never meet today's obligation. `cash_requirement_achievable_on_grid`
is true only when at least one fully constrained plan exists. The separate maximum
today cash value is labeled an upper bound: it ignores subsequent storage feasibility
and cannot by itself prove a feasible complete plan or a willing buyer exists.

## Physical quantity, lot and horizon constraints

The search enumerates sell-today amounts 0, increment, 2×increment, … through total,
plus the full-liquidation endpoint even when total is not an exact multiple of the
decision increment. The total, decision increment and minimum lot must all be
multiples of the **market quantity step**. A nonzero sale must meet the minimum lot.
The market step controls legal sale rounding; the decision increment controls grid
resolution. The grid is capped at 10,000 evaluations; larger requests must choose
a coarser increment rather than silently truncating the search.

Held quantity = total − sold today and must fit initial storage capacity. For each
allowed holding date, daily losses compound:

`remaining_after_day = remaining_before_day × (1 − daily_loss_fraction)`.

The final quantity rounds **down** to the market step. Deterioration loss and final
rounding discard are separately reported, and the future lot must still be marketable.
Loss cannot increase saleable produce. Both deterioration and discard have zero
assumed salvage value. Disposal costs are not included and must be added in a
future extension when material. No optimistic upward quantity rounding occurs.

A plan consists of one sale today plus one later liquidation of the remaining
stock. Different possible later dates are compared separately; this version does
not split remaining stock across multiple future sales, multiple markets or crops.
The selected plan is optimal only on this declared grid and tranche structure,
not a continuous or unrestricted multi-period optimal-control solution.

## Price scenarios and reliability bridge

Each option can contain ordered adverse <= lower <= central <= upper gross selling
prices. Scope, variety/grade, exact target date and issue timestamp must match.
Future-issued scenarios are rejected. A hold plan is recommendation-eligible only
when the service reliability status is validated, flags are empty, and issue date
is the same Indian calendar day as the decision. Older or unreliable scenarios can
be evaluated as scenario-only plans but cannot support the selected hold action.

Use `scenarios_from_reliability(response, adverse_inr_per_quintal=...,
realization_multiplier=..., price_basis_assumption=..., adverse_assumption=...)`
to bridge the prior ReliabilityForecast. It uses the widest supplied nominal band,
multiplies its lower/central/upper wholesale prices by an explicitly supplied farmer
realization factor, and retains reliability, flags, source and version. The mapping
factor is finite in (0,2] and is an assumption, not another calibrated model. The
user must state how grade, quality and quotation basis justify it; reject this
simple mapping if it is inappropriate. The adverse price is separately user-specified
and cannot exceed lower. It is a stress assumption, not a calibrated tail quantile.
Missing point/bands returns None; no future-price triplet is manufactured.

Reliability status is a **trusted backend input**, not something a frontend user
should be allowed to set to validated. The pure mathematical function cannot
authenticate a provider or JSON source claim. A future API must obtain this status
from the reliability service and keep user scenario inputs scenario-only. Current
official forecasting inputs remain unavailable; the example intentionally does
not relabel its prices as validated.

## Objective, comparisons and deterministic selection

For each scenario, total net proceeds = cash today + later net sale proceeds −
storage charges paid later. Upfront storage has already reduced cash today and is
not deducted again. All feasible plans report today's cost ledger, later sale
ledgers at all four scenario prices, central later net, total net by scenario,
adverse/downside total and differences against selling everything today.

Risk objectives (INR utility scores, not scenario probabilities):

| Tolerance | Score |
| --- | --- |
| conservative | adverse total net |
| balanced | .5 × central total net + .5 × adverse total net |
| aggressive | .8 × central total net + .2 × adverse total net |

Scores round to paise. Ties prefer higher downside total, more sold today, then
shorter holding. All price scenarios are shown even though the score uses central
and adverse. Central later proceeds are a planning proxy, **not a probability-weighted
expected value**. Aggressive plans may have negative downside or perform worse than
sell-all-now in adverse conditions; those outcomes remain explicit. A higher score
never overrides cash, storage, lot, duration or reliability constraints.

Break-even future price is the lowest paise-grid price that brings total net back
to sell-all-now under the exact rounded cost accounting, including quantity loss,
extra fixed trip costs, percentage charges and storage timing. A monotone binary
search verifies the settlement threshold up to INR 1 billion/quintal; null means
no break-even in that configured numeric domain. It is not a forecast or cash
feasibility guarantee. No such future price is required for the sell-all-now plan.

Possible outcomes: recommended validated-scenario hold plan, sell_all_now (including
explicit today_only_safe_fallback when forecasts are unreliable/missing),
scenario_only_no_validated_recommendation, no_feasible_cash_solution, or
no_feasible_plan (for example total below minimum marketable lot). An infeasible
case returns no recommended plan, never relaxes mandatory cash, and retains the
sell-all-now ledger and rejection counts for explanation.

## Integration and tests

```python
from app.selling import SellingRequest, optimize_selling

request = SellingRequest.model_validate(your_input_dictionary)
result = optimize_selling(request)
# Keep result Decimals as strings when serializing money to JSON.
```

The response includes schema/units, scope, all input assumptions, selected plan,
best scenario-only-or-validated plan, every feasible grid plan, rejection counts,
sell-all-now comparison and calculation explanations. The CLI optionally saves the
full JSON and prints only a concise summary. Store real farmer inputs privately;
do not commit transaction details or reports as test fixtures.

Unit tests cover net-fee accounting, boundary quantities and lots, exact break-even
paise thresholds, total spoilage, falling prices, high storage costs, upfront
payments, negative returns, crop/horizon/storage constraints, unavailable/unreliable
predictions and risk-dependent downside choices. An exhaustive deterministic
81-case property grid checks quantity conservation, cash/storage constraints and
argmax selection. Ties favor liquidity and inputs remain unchanged.

This engine does not assure a buyer, quality retention or future market price.
Validate local loss/handling assumptions and genuine farmer sale quotations before
using a plan. No Prompt 7 work is included.
