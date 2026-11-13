# Automatic mandi pricing and simpler requests — 13 November 2026

The farmer interface now selects crops using horizontal emoji cards (Tomato, Arecanut,
Onion, Copra and Potato). On small screens the row scrolls horizontally. The crop selects
its configured Karnataka market, variety and grade without asking the farmer for identifiers.

## Automatic price

The advisor reads the latest available dated mandi modal observation. There is no farmer
price-entry field. The backend independently selects the observation when
`use_mandi_price=true`; it does not trust the client-supplied numeric price. The submitted
legacy price field remains in the API contract for compatibility and is overridden in this mode.

Official observations are preferred, with separately identified secondary observations as
a fallback. Selection respects report date, import availability timestamp, exact variety/grade
and INR/quintal units. Missing/nonpositive/incompatible prices or observations older than
seven calendar days fail safely. No freshness limit was relaxed and no data/model was fabricated.

The price is a wholesale reference used as an estimated realization basis, not a buyer's
confirmed offer. Source/date and this limitation are visible; recommendations carry a
machine-readable warning. Historical market data and forecast uncertainty remain distinct
from final quality, transaction price, fees and farmer realization.

## Two-field request form

The farmer selects a crop card, enters the quantity and preferred arrival time, reviews
the server-selected reference price and confirms. Variety/grade/mandi are filled from the
selected crop scope. Harvest quantity is carried from the current plan when applicable.
Costs, message and consent to share a verified phone number are optional details.
The form explicitly states that unentered fees/transport are excluded. Preview values
are reference estimates, not a guaranteed net settlement. Final offer and actual sale
records remain separate.

Preview returns the exact server-selected price. Confirmation checks that price again;
a changed observation returns 409 and requires another review rather than silently changing
terms. Creation retains its per-farmer idempotency key through retries.

## Mandi activation and truthful delivery

Previously a mandi without an onboarded owner blocked submission. Farmers can now save
a durable request for an authentic market/crop while onboarding is incomplete:

- Business state: SUBMITTED.
- Delivery state: WAITING_FOR_MANDI_ACTIVATION.
- No owner notification or external delivery is claimed.
- The farmer can view/cancel the request.

When a real approved owner redeems their invitation, or an administrator activates an
already assigned mandi, waiting requests for accepted crops are atomically released to
NOTIFIED and their in-app notifications/outbox records are created. Version checks and
notification uniqueness prevent duplicate release. Arrival dates that already passed are
expired; cancelled requests are never released. An administrator's deliberate inactive/paused
registration still rejects new requests. Cancelled/expired requests that were never notified
report NOT_SENT rather than claiming delivery.

This reuses existing states/tables and requires no schema migration or replacement of
the running database. Existing user accounts and histories are preserved. Ownership and
staff permissions are unchanged. A farmer opening `/mandi` now sees a clear explanation,
a return-to-farmer link and a button to sign in using an approved operator account;
operator navigation is hidden until the correct role signs in. No farmer is promoted and
no owner account/contact is fabricated.

## Verification

Actually executed:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --tb=short
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe scripts/run_e2e.py
.\.venv\Scripts\python.exe scripts/run_sale_e2e.py
```

- 183 backend tests passed, including client-price override, missing/stale quote rejection,
  pending idempotency, activation release, cancellation safety and existing privacy controls.
- 34 frontend tests passed; frontend lint/typecheck/build passed.
- 3 actual HTTP integration tests passed with server-derived prices and computed proceeds.
- Actual Chromium passed: farmer saves a pending automatically priced request -> approved
  owner onboards -> notification arrives -> counteroffer -> farmer confirmation -> arrival,
  weighment and completion. No page errors. All identities/transactions are disposable TEST_ONLY.
- Five horizontal crop cards and automatic prices were checked against the running local
  authentic dataset. Kannada mobile layout has no horizontal page overflow.
- Existing Vite bundle-size and Starlette/httpx deprecation warnings remain.

The browser sale fixture uses an explicitly labeled current TEST_ONLY quote inserted AFTER
training/calibration. This allows real-clock freshness checks without weakening them or
altering saved model evaluations. That fixture never enters the running local database.

Evidence: reports/mandi-price-backend-all.log, mandi-price-frontend-tests.log,
mandi-price-http-e2e.log, mandi-price-browser-e2e.log, mandi-price-local-quotes.json,
mandi-price-crop-cards-desktop.png and mandi-price-crop-cards-mobile-kn.png.

Real owner onboarding is still required for a request to reach a real mandi operator.
External messaging still requires configured providers, verified contacts and consent;
real SMTP/SMS/WhatsApp delivery has not been tested. A pending record is not an accepted
offer, confirmed booking, executed commodity sale or payment.
