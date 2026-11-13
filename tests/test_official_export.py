import importlib.util
from datetime import date
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("official_export", Path(__file__).parents[1] / "scripts/archive_official_export.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_official_prelude_conversion_preserves_source_fields_and_grade():
    raw = (',Daily Price Report TEST_ONLY\r\n\r\nState/UT,District,Market,Commodity,Variety,Grade,Min Price,Max Price,Modal Price,Price Unit,Price Date\r\n'
           'Karnataka,Kolar,Kolar APMC,Tomato,Tomato,Local,900,1200,1000,Rs./Quintal,01-01-2021\r\n').encode()
    converted, n = module.convert(raw, None, date(2021, 1, 1), date(2021, 12, 31))
    assert n == 1 and b"Tomato,Tomato,Local,900,1200,1000,Rs./Quintal,01-01-2021" in converted
    assert converted.startswith(b"State,District,Market,Commodity,Variety,Grade,Min_Price")
    with pytest.raises(ValueError, match="outside"):
        module.convert(raw, None, date(2022, 1, 1), date(2022, 12, 31))
    with pytest.raises(ValueError, match="unit"):
        module.convert(raw.replace(b"Rs./Quintal", b"USD/kg"), None, date(2021, 1, 1), date(2021, 12, 31))
