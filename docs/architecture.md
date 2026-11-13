# Foundation and next implementation boundary

Update: the CSV ingestion stage now adds ImportBatch / ImportRow audit entities,
grade/data-kind business keys, nullable arrivals and versioned market/history
endpoints. See [ingestion](ingestion.md) for the current operational contract.
The notes below document the initial foundation and its ML boundary.

SAMAY is a decision-support foundation for Team Resonance at COLOSSUS 3.0.
There is no trained model, forecast endpoint, live ingestion, or recommendation engine yet.

The React client calls process liveness at `/api/health`. FastAPI reserves an
`APIRouter` prefix `/api/v1` for future features. Alembic owns schema changes;
application startup does not silently create or mutate tables.

Markets and commodities identify mandi observations. Observations have a calendar
date, variety, explicit INR/quintal prices, arrivals in quintals, and provenance.
Model versions link to predictions; predictions retain their target date, interval
bounds and nominal coverage. Recommendations reference predictions and store
quantity, immediate cash requirement, holding cost, action and rationale. Bounds
and monetary constraints are enforced in SQLite; foreign keys are enabled on every
application connection. Decimal money is stored as Numeric; SQLite does not offer
the same exact numeric enforcement as a production decimal database.

All timestamps pass through UTCDateTime: aware input is normalized to UTC and
naive input is rejected; SQLite values are rehydrated with UTC tzinfo. Calendar
dates deliberately have no timezone. DEMO_DATA records are synthetic and must be
excluded from all future training and evaluation. No predictions are seeded.

Next: agree on a licensed data source and ingestion contract, validate commodity,
variety and market identifiers, detect missing/duplicate observations, and track
provenance. Establish chronological holdout/backtests and simple baselines before
training LightGBM. Evaluate interval calibration and leakage. Define spoilage,
storage costs, fees and cash constraints before implementing sell/hold decisions.
Expose validated versioned endpoints with tests, then connect frontend forms.
Add authentication and deployment controls before storing farmer-specific data.
