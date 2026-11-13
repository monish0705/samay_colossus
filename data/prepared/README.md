# Portable official-data database

`samay.db` contains 1,943 imported official observations and 3 separately labeled
fixtures. Recommendation history is empty. Actual fetch timestamps, report dates,
source rows and original units are preserved. Archive paths are relative to the
repository root. `manifest.json` records the database SHA256.

From the repository root after dependency setup:

```powershell
.\.venv\Scripts\python.exe scripts/start_local.py
```

Startup verifies and restores this copy only when the default local `samay.db`
does not exist. Existing local databases and custom database configurations are
preserved. Research models and reports are included under `models/research/` and
`reports/research/`; they are not validated live forecasts. Treat pickle artifacts
as executable trusted inputs and retain the registry/model hash checks.
