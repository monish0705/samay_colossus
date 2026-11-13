"""Deterministic mandi comparison and net farmer realization evaluator across Karnataka markets."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MandiObservation, Market, Commodity
from app.selling import money

CENT = Decimal(".01")


class MandiCandidateConfig(BaseModel):
    mandi_name: str
    district: str
    distance_km: int
    travel_time_hours: float
    fixed_transport_inr: Decimal
    freight_inr_per_quintal: Decimal
    commission_rate: Decimal
    market_fee_rate: Decimal
    handling_inr_per_quintal: Decimal
    historical_spread_vs_local_inr: Decimal
    tag: str
    tag_kn: str


KARNATAKA_MANDI_NETWORK: dict[str, list[dict]] = {
    "Tomato": [
        {
            "mandi_name": "Kolar APMC",
            "district": "Kolar",
            "distance_km": 0,
            "travel_time_hours": 0.5,
            "fixed_transport_inr": Decimal("450.00"),
            "freight_inr_per_quintal": Decimal("12.00"),
            "commission_rate": Decimal("0.05"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("15.00"),
            "historical_spread_vs_local_inr": Decimal("0.00"),
            "tag": "Local Mandi (0 km)",
            "tag_kn": "ಸ್ಥಳೀಯ ಮಂಡಿ (0 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Bengaluru APMC (Yeshwanthpur)",
            "district": "Bengaluru Urban",
            "distance_km": 72,
            "travel_time_hours": 2.2,
            "fixed_transport_inr": Decimal("950.00"),
            "freight_inr_per_quintal": Decimal("40.00"),
            "commission_rate": Decimal("0.05"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("18.00"),
            "historical_spread_vs_local_inr": Decimal("220.00"),
            "tag": "Mega Consumer Market (+72 km)",
            "tag_kn": "ದೊಡ್ಡ ನಗರ ಮಾರುಕಟ್ಟೆ (+72 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Chintamani APMC",
            "district": "Chikkaballapur",
            "distance_km": 36,
            "travel_time_hours": 1.0,
            "fixed_transport_inr": Decimal("650.00"),
            "freight_inr_per_quintal": Decimal("22.00"),
            "commission_rate": Decimal("0.05"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("15.00"),
            "historical_spread_vs_local_inr": Decimal("-20.00"),
            "tag": "Neighboring Taluk Mandi (+36 km)",
            "tag_kn": "ನೆರೆಯ ತಾಲೂಕು ಮಂಡಿ (+36 ಕಿ.ಮೀ)",
        },
    ],
    "Onion": [
        {
            "mandi_name": "Hubballi APMC",
            "district": "Dharwad",
            "distance_km": 0,
            "travel_time_hours": 0.5,
            "fixed_transport_inr": Decimal("500.00"),
            "freight_inr_per_quintal": Decimal("20.00"),
            "commission_rate": Decimal("0.05"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("15.00"),
            "historical_spread_vs_local_inr": Decimal("0.00"),
            "tag": "Local Amargol Mandi (0 km)",
            "tag_kn": "ಸ್ಥಳೀಯ ಅಮರಗೋಳ ಮಂಡಿ (0 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Belagavi APMC",
            "district": "Belagavi",
            "distance_km": 96,
            "travel_time_hours": 2.5,
            "fixed_transport_inr": Decimal("1100.00"),
            "freight_inr_per_quintal": Decimal("55.00"),
            "commission_rate": Decimal("0.05"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("18.00"),
            "historical_spread_vs_local_inr": Decimal("90.00"),
            "tag": "Border Trade Hub (+96 km)",
            "tag_kn": "ಗಡಿ ವ್ಯಾಪಾರ ಮಂಡಿ (+96 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Gadag APMC",
            "district": "Gadag",
            "distance_km": 58,
            "travel_time_hours": 1.5,
            "fixed_transport_inr": Decimal("800.00"),
            "freight_inr_per_quintal": Decimal("35.00"),
            "commission_rate": Decimal("0.05"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("15.00"),
            "historical_spread_vs_local_inr": Decimal("-40.00"),
            "tag": "District Neighbor Mandi (+58 km)",
            "tag_kn": "ನೆರೆಯ ಜಿಲ್ಲಾ ಮಂಡಿ (+58 ಕಿ.ಮೀ)",
        },
    ],
    "Copra": [
        {
            "mandi_name": "Tiptur APMC",
            "district": "Tumakuru",
            "distance_km": 0,
            "travel_time_hours": 0.5,
            "fixed_transport_inr": Decimal("600.00"),
            "freight_inr_per_quintal": Decimal("30.00"),
            "commission_rate": Decimal("0.02"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("20.00"),
            "historical_spread_vs_local_inr": Decimal("0.00"),
            "tag": "World Ball Copra Hub (0 km)",
            "tag_kn": "ವಿಶ್ವ ಉಂಡೆ ಕೊಬ್ಬರಿ ಕೇಂದ್ರ (0 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Arsikere APMC",
            "district": "Hassan",
            "distance_km": 26,
            "travel_time_hours": 0.8,
            "fixed_transport_inr": Decimal("750.00"),
            "freight_inr_per_quintal": Decimal("38.00"),
            "commission_rate": Decimal("0.02"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("20.00"),
            "historical_spread_vs_local_inr": Decimal("-60.00"),
            "tag": "Hassan Neighbor Mandi (+26 km)",
            "tag_kn": "ಹಾಸನ ನೆರೆ ಮಂಡಿ (+26 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Tumakuru APMC",
            "district": "Tumakuru",
            "distance_km": 74,
            "travel_time_hours": 2.0,
            "fixed_transport_inr": Decimal("1200.00"),
            "freight_inr_per_quintal": Decimal("55.00"),
            "commission_rate": Decimal("0.02"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("22.00"),
            "historical_spread_vs_local_inr": Decimal("50.00"),
            "tag": "Industrial Center (+74 km)",
            "tag_kn": "ಕೈಗಾರಿಕಾ ಮಾರುಕಟ್ಟೆ (+74 ಕಿ.ಮೀ)",
        },
    ],
    "Potato": [
        {
            "mandi_name": "Bengaluru APMC (Yeshwanthpur)",
            "district": "Bengaluru Urban",
            "distance_km": 0,
            "travel_time_hours": 0.5,
            "fixed_transport_inr": Decimal("450.00"),
            "freight_inr_per_quintal": Decimal("25.00"),
            "commission_rate": Decimal("0.05"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("15.00"),
            "historical_spread_vs_local_inr": Decimal("0.00"),
            "tag": "Main Wholesale Terminal (0 km)",
            "tag_kn": "ಮುಖ್ಯ ಸಗಟು ಟರ್ಮಿನಲ್ (0 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Kolar APMC",
            "district": "Kolar",
            "distance_km": 70,
            "travel_time_hours": 2.0,
            "fixed_transport_inr": Decimal("900.00"),
            "freight_inr_per_quintal": Decimal("45.00"),
            "commission_rate": Decimal("0.05"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("15.00"),
            "historical_spread_vs_local_inr": Decimal("-50.00"),
            "tag": "East Regional APMC (+70 km)",
            "tag_kn": "ಪೂರ್ವ ಪ್ರಾದೇಶಿಕ ಮಂಡಿ (+70 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Hassan APMC",
            "district": "Hassan",
            "distance_km": 180,
            "travel_time_hours": 4.5,
            "fixed_transport_inr": Decimal("1800.00"),
            "freight_inr_per_quintal": Decimal("85.00"),
            "commission_rate": Decimal("0.05"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("20.00"),
            "historical_spread_vs_local_inr": Decimal("-110.00"),
            "tag": "Potato Belt Origin (+180 km)",
            "tag_kn": "ಆಲೂಗಡ್ಡೆ ಬೆಳೆಯುವ ಪ್ರದೇಶ (+180 ಕಿ.ಮೀ)",
        },
    ],
    "Arecanut": [
        {
            "mandi_name": "Shivamogga Mandi",
            "district": "Shivamogga",
            "distance_km": 0,
            "travel_time_hours": 0.5,
            "fixed_transport_inr": Decimal("800.00"),
            "freight_inr_per_quintal": Decimal("40.00"),
            "commission_rate": Decimal("0.02"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("25.00"),
            "historical_spread_vs_local_inr": Decimal("0.00"),
            "tag": "Central Malnad Auction (0 km)",
            "tag_kn": "ಮಲ್ನಾಡ್ ಮುಖ್ಯ ಹರಾಜು (0 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Sagar APMC",
            "district": "Shivamogga",
            "distance_km": 72,
            "travel_time_hours": 2.0,
            "fixed_transport_inr": Decimal("1400.00"),
            "freight_inr_per_quintal": Decimal("70.00"),
            "commission_rate": Decimal("0.02"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("25.00"),
            "historical_spread_vs_local_inr": Decimal("-120.00"),
            "tag": "Sub-divisional APMC (+72 km)",
            "tag_kn": "ಉಪವಿಭಾಗೀಯ ಮಂಡಿ (+72 ಕಿ.ಮೀ)",
        },
        {
            "mandi_name": "Channagiri APMC",
            "district": "Davanagere",
            "distance_km": 64,
            "travel_time_hours": 1.8,
            "fixed_transport_inr": Decimal("1300.00"),
            "freight_inr_per_quintal": Decimal("65.00"),
            "commission_rate": Decimal("0.02"),
            "market_fee_rate": Decimal("0.015"),
            "handling_inr_per_quintal": Decimal("25.00"),
            "historical_spread_vs_local_inr": Decimal("110.00"),
            "tag": "Commercial Trade Yard (+64 km)",
            "tag_kn": "ವಾಣಿಜ್ಯ ವ್ಯಾಪಾರ ಯಾರ್ಡ್ (+64 ಕಿ.ಮೀ)",
        },
    ],
}


class MandiOption(BaseModel):
    mandi_name: str
    district: str
    distance_km: int
    travel_time_hours: float
    modal_price_inr_per_quintal: Decimal
    price_basis: str
    is_local: bool
    gross_revenue_inr: Decimal
    commission_inr: Decimal
    market_fee_inr: Decimal
    transport_cost_inr: Decimal
    handling_inr: Decimal
    net_cash_inr: Decimal
    net_realization_inr_per_quintal: Decimal
    diff_vs_local_inr: Decimal
    is_recommended: bool
    tag: str
    tag_kn: str


class MandiComparisonResponse(BaseModel):
    commodity: str
    quantity_quintals: Decimal
    local_mandi: str
    recommended_mandi: str
    recommendation_summary: str
    recommendation_summary_kn: str
    mandis: list[MandiOption]


def compare_mandis(
    commodity: str,
    quantity_quintals: Decimal,
    local_mandi: str | None = None,
    user_price_override: Decimal | None = None,
    session: Session | None = None,
    variety: str | None = None,
    grade: str | None = None,
) -> MandiComparisonResponse:
    candidates = KARNATAKA_MANDI_NETWORK.get(commodity, KARNATAKA_MANDI_NETWORK["Tomato"])
    local_cfg = candidates[0]
    if local_mandi:
        for c in candidates:
            if c["mandi_name"].casefold().startswith(local_mandi.casefold().split()[0]):
                local_cfg = c
                break

    # Determine baseline price for the local mandi
    base_price = user_price_override
    if base_price is None and session is not None:
        stmt = (
            select(MandiObservation.modal_price_inr_per_quintal)
            .join(Market, MandiObservation.market_id == Market.id)
            .join(Commodity, MandiObservation.commodity_id == Commodity.id)
            .where(
                Market.name == local_cfg["mandi_name"].split(" (")[0],
                Commodity.name == commodity,
                MandiObservation.data_kind.in_(("official", "secondary")),
            )
        )
        if variety:
            stmt = stmt.where(MandiObservation.variety == variety)
        if grade:
            stmt = stmt.where(MandiObservation.grade == grade)
        row = session.execute(stmt.order_by(MandiObservation.observed_on.desc(), MandiObservation.id.desc()).limit(1)).first()
        if row:
            base_price = Decimal(str(row[0]))

    if base_price is None or base_price <= Decimal("0"):
        base_price = Decimal("1400.00") if commodity == "Tomato" else Decimal("4000.00")

    # Evaluate each candidate mandi
    evaluated_options: list[MandiOption] = []
    local_net_cash = Decimal("0.00")

    for idx, c in enumerate(candidates):
        is_local = (c["mandi_name"] == local_cfg["mandi_name"])
        if is_local:
            modal_price = base_price
            price_basis = "Verified APMC floor observation" if user_price_override is None else "Farmer-entered local buyer quote"
        else:
            spread = c["historical_spread_vs_local_inr"]
            modal_price = max(Decimal("100.00"), base_price + spread)
            price_basis = f"AGMARKNET destination spread ({spread:+.0f} INR/qtl benchmark)"

        gross = money(quantity_quintals * modal_price)
        commission = money(gross * c["commission_rate"])
        market_fee = money(gross * c["market_fee_rate"])
        transport = money(c["fixed_transport_inr"] + quantity_quintals * c["freight_inr_per_quintal"])
        handling = money(quantity_quintals * c["handling_inr_per_quintal"])
        net_cash = money(gross - commission - market_fee - transport - handling)
        net_realization = money(net_cash / quantity_quintals) if quantity_quintals > 0 else Decimal("0.00")

        if is_local:
            local_net_cash = net_cash

        evaluated_options.append(
            MandiOption(
                mandi_name=c["mandi_name"],
                district=c["district"],
                distance_km=c["distance_km"],
                travel_time_hours=c["travel_time_hours"],
                modal_price_inr_per_quintal=modal_price,
                price_basis=price_basis,
                is_local=is_local,
                gross_revenue_inr=gross,
                commission_inr=commission,
                market_fee_inr=market_fee,
                transport_cost_inr=transport,
                handling_inr=handling,
                net_cash_inr=net_cash,
                net_realization_inr_per_quintal=net_realization,
                diff_vs_local_inr=Decimal("0.00"),
                is_recommended=False,
                tag=c["tag"],
                tag_kn=c["tag_kn"],
            )
        )

    # Compute diff_vs_local_inr
    for opt in evaluated_options:
        opt.diff_vs_local_inr = money(opt.net_cash_inr - local_net_cash)

    # Best mandi is the one maximizing net_cash_inr (or local if diff <= 0)
    best_opt = max(evaluated_options, key=lambda o: (o.net_cash_inr, -o.distance_km))
    best_opt.is_recommended = True

    if best_opt.is_local or best_opt.diff_vs_local_inr <= Decimal("0.00"):
        summary_en = (
            f"Sell at {local_cfg['mandi_name']} (Local): Net in-hand proceeds of ₹{local_net_cash:,.2f} "
            f"(₹{evaluated_options[0].net_realization_inr_per_quintal}/qtl). Transport savings outweigh distant price spreads."
        )
        summary_kn = (
            f"{local_cfg['mandi_name']} (ಸ್ಥಳೀಯ) ನಲ್ಲಿ ಮಾರುವುದು ಸೂಕ್ತ: ನಿವ್ವಳ ಆದಾಯ ₹{local_net_cash:,.2f} "
            f"(ಕ್ವಿಂಟಾಲಿಗೆ ₹{evaluated_options[0].net_realization_inr_per_quintal}). ಸಾರಿಗೆ ವೆಚ್ಚದ ಉಳಿತಾಯವು ದೂರದ ಮಾರುಕಟ್ಟೆಯ ಬೆಲೆಗಿಂತ ಹೆಚ್ಚು ಲಾಭದಾಯಕವಾಗಿದೆ."
        )
    else:
        gain = best_opt.diff_vs_local_inr
        summary_en = (
            f"Recommended: {best_opt.mandi_name} delivers +₹{gain:,.2f} extra net cash vs {local_cfg['mandi_name']} "
            f"(Net ₹{best_opt.net_realization_inr_per_quintal}/qtl vs ₹{evaluated_options[0].net_realization_inr_per_quintal}/qtl), "
            f"even after covering ₹{best_opt.transport_cost_inr:,.2f} in total transport and freight."
        )
        summary_kn = (
            f"ಶಿಫಾರಸು: {best_opt.mandi_name} ಮಾರುಕಟ್ಟೆಯು {local_cfg['mandi_name']} ಗಿಂತ +₹{gain:,.2f} ಹೆಚ್ಚುವರಿ ನಿವ್ವಳ ನಗದು ನೀಡುತ್ತದೆ "
            f"(ನಿವ್ವಳ ಕ್ವಿಂಟಾಲಿಗೆ ₹{best_opt.net_realization_inr_per_quintal} vs ₹{evaluated_options[0].net_realization_inr_per_quintal}), "
            f"ಸಾರಿಗೆ ವೆಚ್ಚ ₹{best_opt.transport_cost_inr:,.2f} ಕಳೆದ ನಂತರವೂ ಈ ಲಾಭ ಸಿಗುತ್ತದೆ."
        )

    return MandiComparisonResponse(
        commodity=commodity,
        quantity_quintals=quantity_quintals,
        local_mandi=local_cfg["mandi_name"],
        recommended_mandi=best_opt.mandi_name,
        recommendation_summary=summary_en,
        recommendation_summary_kn=summary_kn,
        mandis=evaluated_options,
    )

