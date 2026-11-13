import sys
from decimal import Decimal
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.mandi_comparison import compare_mandis, MandiComparisonResponse


def test_mandi_comparison_tomato_arbitrage():
    # 30 quintals of Tomato from Kolar
    res = compare_mandis(
        commodity="Tomato",
        quantity_quintals=Decimal("30"),
        local_mandi="Kolar APMC",
        user_price_override=Decimal("1400.00"),
    )
    assert isinstance(res, MandiComparisonResponse)
    assert res.commodity == "Tomato"
    assert res.quantity_quintals == Decimal("30")
    assert len(res.mandis) == 3
    
    local = next(m for m in res.mandis if m.is_local)
    assert local.mandi_name == "Kolar APMC"
    assert local.diff_vs_local_inr == Decimal("0.00")
    
    # Bengaluru APMC should be recommended for 30 qtl due to destination premium
    bengaluru = next(m for m in res.mandis if "Bengaluru" in m.mandi_name)
    assert bengaluru.diff_vs_local_inr > Decimal("0.00")
    assert bengaluru.is_recommended is True
    assert "Bengaluru APMC" in res.recommended_mandi
    assert res.recommendation_summary_kn is not None
    assert len(res.recommendation_summary_kn) > 10


def test_mandi_comparison_small_quantity_stays_local():
    # 2 quintals: transport to Bengaluru should NOT justify the trip
    res = compare_mandis(
        commodity="Tomato",
        quantity_quintals=Decimal("2"),
        local_mandi="Kolar APMC",
        user_price_override=Decimal("1400.00"),
    )
    local = next(m for m in res.mandis if m.is_local)
    assert local.is_recommended is True
    assert res.recommended_mandi == "Kolar APMC"


def test_mandi_comparison_all_crops():
    crops = ["Arecanut", "Onion", "Copra", "Potato"]
    for crop in crops:
        res = compare_mandis(
            commodity=crop,
            quantity_quintals=Decimal("10"),
        )
        assert res.commodity == crop
        assert len(res.mandis) >= 2
        assert any(m.is_recommended for m in res.mandis)

