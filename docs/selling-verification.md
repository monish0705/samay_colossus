# Prompt 6 verification — 2026-11-04

## Files changed

Added backend/app/selling.py, scripts/optimize_selling.py,
tests/test_selling.py, docs/examples/selling-example.json, docs/selling.md and
this verification record. README.md links to the selling workflow. No database
schema, forecast model, reliability policy or frontend implementation changed.
The example report is generated under ignored reports/selling-example.json.

## Exact commands and outputs

PowerShell from repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_selling.py -q
```

```text
25 passed in 1.17s
```

Tests include an exhaustive deterministic 81-case property grid for cash/storage
constraints, quantity conservation and objective maximization. Other tests cover
explicit fees and fixed costs, break-even thresholds to the paise, zero storage,
insufficient cash, negative returns, falling future prices, expensive storage,
complete loss, minimum lot and terminal-grid boundaries, upfront charges,
scope/time/schedule validation, input immutability, liquidity tie breaking,
unavailable predictions and the trusted reliability adapter.

```powershell
.\.venv\Scripts\python.exe scripts/optimize_selling.py --input docs/examples/selling-example.json --output reports/selling-example.json
```

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

This is the requested **illustrative**, configurable 20-quintal/INR 10,000 cash
example, not a live price forecast or fixed farmer instruction. Its hypothetical
future prices are scenario-only. The full report retains eight conditional holding
plans and one sell-all plan, while the selected safe recommendation is sell-all.
Inspection of the saved JSON confirmed:

```json
{
  "safe_recommendation": "20",
  "example_only_alternative_eligible": false,
  "alternative_sell_today_quintals": "11",
  "alternative_hold_quintals": "9",
  "cash_today_inr": "10240.00",
  "rejection_counts": {
    "storage_capacity": 10,
    "immediate_net_cash_shortfall": 1,
    "future_quantity_below_minimum_lot_after_loss": 1
  }
}
```

The alternative is calculated for scenario inspection only, not promoted to a
validated hold recommendation. Full transaction ledgers, all four scenario
outcomes, downside differences, physical loss/rounding discards and break-even
prices are preserved in the report.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

```text
66 passed, 1 warning in 47.65s
```

The warning is the pre-existing Starlette TestClient HTTPX deprecation. No new
dependencies were needed.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
git diff --check
```

```text
No broken requirements found.
No new upgrade operations detected.
```

Whitespace check emitted no errors. Frontend tests were not rerun because no
frontend code changed.

## Limitations and handoff

The engine optimizes the declared grid with one today tranche and one future
liquidation date; it is not unrestricted multi-date inventory optimization.
Storage conditions, loss schedules, holding limits, realized sale-price mapping
and cost quotations require local verification. No universal spoilage percentage
or tomato shelf life was hardcoded. Central proceeds are a planning scenario,
not a statistical expected return or guarantee.

The service still lacks authenticated historical forecasts from earlier stages.
Its unavailable response maps to missing scenarios, triggering the explicit safe
fallback. Production integration must obtain validated status from the trusted
reliability backend, not a user-editable JSON field. Calibrated wholesale-price
uncertainty must not be advertised as farmer-specific transaction-price certainty.

Next handoff: connect farmer-entered quantities/actual buyer quotations and locally
verified storage/cost assumptions to this function; pass forecast scenarios only
through the trusted service adapter. No Prompt 7 work was started.
