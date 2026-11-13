# Simplified farmer interface — 13 November 2026

The subsequent [automatic mandi-price update](MANDI-PRICE-AND-REQUESTS.md) replaces the
buyer-quote field below with a dated backend-selected reference and horizontal emoji crop
cards. The three-step structure and advanced settings remain.

Removed the Judge/Farmer mode switch, timed demonstration, guided tour and example-loading
controls. The application has one farmer experience, while the authenticated mandi portal
remains separate. Less frequently used navigation links are under More tools.

The advisor now uses three steps:

1. **Crop and cash:** crop/market, harvest quantity, farmer buyer quotation and cash need.
   An optional disclosure allows a later cash deadline. Official dated prices remain
   references and do not silently populate a farmer buyer quotation.
2. **Storage and costs:** yes/no storage choice. No storage skips the holding fields.
   Available storage shows capacity, safe duration, daily storage cost and estimated loss.
   Transport and commission remain visible. Detailed fees, lot sizes, source notes,
   advanced storage assumptions and weather/price scenarios are available under More options.
   Selecting a safe duration also sets the holding ceiling, avoiding a second required
   technical question. Advanced overrides remain available and are validated.
3. **Review your plan:** inspect values and costs, acknowledge assumptions and calculate
   through the existing backend. No financial/model logic was moved into the browser.

Crop costs and loss estimates still require local verification. Forecast availability,
cash constraints, uncertainty, deterioration and rounding continue to be enforced by
the existing services. The long explanatory side panel and duplicate harvest/cash pages
were removed. Detailed calculation audit remains available in Results without a mode switch.

Verification actually executed:

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe scripts/run_e2e.py
.\.venv\Scripts\python.exe scripts/run_sale_e2e.py
```

- Frontend: 33 tests passed; lint/typecheck/production build passed.
- Real HTTP integration: 3 tests passed against an isolated saved-model/optimizer fixture.
- Actual Chromium: recommendation -> sale request -> owner notification/counteroffer ->
  farmer confirmation -> arrival/weighment/completion passed with zero page errors.
- Fresh 390px mobile views and desktop checked in English/Kannada; no horizontal overflow.
- Browser checks verify three steps, removed presentation controls, preserved quantities
  after language changes, collapsed advanced settings and safe-duration selection.
- Existing Vite bundle-size warning remains. Backend financial services/models were unchanged.

Evidence: reports/simple-advisor-tests.log, simple-advisor-http-e2e.log,
simple-advisor-sale-e2e.log, simple-advisor-browser.json, simple-advisor-desktop.png,
simple-advisor-mobile-en.png and simple-advisor-mobile-kn.png.

The browser/HTTP fixtures remain isolated TEST_ONLY data. The running local application
uses its authentic prepared history and saved artifacts; no real sale transactions were seeded.
