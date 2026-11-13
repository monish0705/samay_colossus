"""No-network tests of the public response validator; values are TEST_ONLY."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("fetch_official_recent", Path(__file__).parents[1] / "scripts/fetch_official_recent.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def response():
    return {"success": True, "columns": [{"key": "variety"}, {"key": "2026-01-01"}, {"key": "2026-01-02"}, {"key": "unitOfPrice"}],
        "data": [{"variety": "Kolar APMC - TEST_ONLY", "unitOfPrice": "Rs./Quintal", "2026-01-01": 1000, "2026-01-02": "NR"}]}


def test_recent_preserves_missing_dates_without_fabricating_fields():
    observations, missing = module.parse_recent(response())
    assert len(observations) == len(missing) == 1
    assert "min_price_inr_per_quintal" not in observations[0]
    assert observations[0]["price_unit"] == "INR/quintal"


@pytest.mark.parametrize("value", [-1, "NaN", "Infinity"])
def test_recent_rejects_invalid_prices(value):
    payload = response()
    payload["data"][0]["2026-01-01"] = value
    with pytest.raises(ValueError):
        module.parse_recent(payload)
