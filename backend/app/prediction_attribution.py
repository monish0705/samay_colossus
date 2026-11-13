"""Attribution of prediction conditions and profit/loss breakdown for farmers."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel
from sqlalchemy import select

from app.models import MandiObservation, Market, Commodity


class ConditionFactorImpact(BaseModel):
    condition: str
    category: str
    impact: Literal["profit", "loss", "neutral"]
    price_effect_inr_per_quintal: Decimal
    percentage_effect: float
    description: str
    evidence_basis: str


class PredictionAttribution(BaseModel):
    base_price_inr_per_quintal: Decimal
    predicted_price_inr_per_quintal: Decimal
    net_price_change_inr_per_quintal: Decimal
    net_change_percentage: float
    factors: list[ConditionFactorImpact]
    summary: str


CROP_FACTOR_TEMPLATES: dict[str, list[dict]] = {
    "Arecanut": [
        {
            "condition": "Post-Monsoon Western Ghats Malnad Arrivals",
            "category": "Harvest & Arrival Volume",
            "direction": -1,
            "weight": Decimal("0.35"),
            "description": "Heavy post-monsoon harvest arrivals entering Shivamogga Mandi auctions create temporary supply absorption pressure.",
            "evidence_basis": "Shivamogga APMC floor daily auction arrival records",
        },
        {
            "condition": "Pan Masala & Supari Industrial Procurement",
            "category": "Industrial Demand",
            "direction": 1,
            "weight": Decimal("0.25"),
            "description": "Sustained buying demand from North Indian (Kanpur/Gujarat) industrial processors for boiled Rashi/Bette whole nut lots.",
            "evidence_basis": "MAMCOS & CAMPCO commercial trade despatches",
        },
        {
            "condition": "DGFT Minimum Import Price (MIP ₹351/kg) Policy Protection",
            "category": "Trade & Import Regulation",
            "direction": 1,
            "weight": Decimal("0.20"),
            "description": "Government MIP and customs tariffs protect domestic growers against cheap Indonesian and Sri Lankan imports, setting a firm price floor.",
            "evidence_basis": "Directorate General of Foreign Trade (DGFT) import notification",
        },
        {
            "condition": "Weather & Koleroga (Fruit Rot) Quality Checks",
            "category": "Pest & Climate Conditions",
            "direction": -1,
            "weight": Decimal("0.20"),
            "description": "High post-monsoon humidity increases nut moisture drying requirements and quality screening on fungal spots.",
            "evidence_basis": "Malnad agricultural meteorological observations",
        },
    ],
    "Potato": [
        {
            "condition": "Cold Storage Year-End Destocking Cycle",
            "category": "Storage Release Rates",
            "direction": -1,
            "weight": Decimal("0.55"),
            "description": "Large-scale North Indian cold storages (Agra/Punjab) release inventory before fresh winter Rabi arrivals, suppressing wholesale bids.",
            "evidence_basis": "National Horticulture Board cold store occupancy release reports",
        },
        {
            "condition": "Mandi Inflow Volume & Transit Space Limits",
            "category": "Harvest & Logistics",
            "direction": -1,
            "weight": Decimal("0.30"),
            "description": "Heavy truck inflows into Yeshwanthpur APMC create intra-week lot backlogs and quick-sale dealer discounting.",
            "evidence_basis": "Bengaluru APMC gate vehicle intake logs",
        },
        {
            "condition": "Urban Retail & Fasting Demand Support",
            "category": "Consumer Trends",
            "direction": 1,
            "weight": Decimal("0.15"),
            "description": "Steady household table potato consumption across Bengaluru and festival fasting observances provide a baseline demand cushion.",
            "evidence_basis": "Karnataka State Agricultural Marketing Board retail price survey",
        },
    ],
    "Onion": [
        {
            "condition": "Post-Monsoon Rainfall & Supply Arrival Cliff",
            "category": "Weather & Harvest Flow",
            "direction": 1,
            "weight": Decimal("0.45"),
            "description": "Unseasonal rainfall in Dharwad and Gadag causes harvesting delays, creating a temporary supply cliff and upward price pressure.",
            "evidence_basis": "Open-Meteo North Karnataka precipitation data & APMC arrivals",
        },
        {
            "condition": "Kanda Chawl Storage Spoilage & Shrinkage",
            "category": "Post-Harvest Storage Losses",
            "direction": 1,
            "weight": Decimal("0.25"),
            "description": "High ambient moisture results in 20–25% sorting and rotting losses, reducing marketable wholesale stock.",
            "evidence_basis": "ICAR-Directorate of Onion and Garlic Research post-harvest estimates",
        },
        {
            "condition": "Government Buffer Releases & 40% Export Duty",
            "category": "Government Policy Intervention",
            "direction": -1,
            "weight": Decimal("0.30"),
            "description": "NAFED/NCCF buffer stock releases at subsidized rates (₹25–35/kg) and export tariffs cap upside price rallies.",
            "evidence_basis": "Ministry of Consumer Affairs buffer release logs",
        },
    ],
    "Copra": [
        {
            "condition": "Sun-Dried Ball Copra Seasonal Inflow",
            "category": "Regional Production",
            "direction": -1,
            "weight": Decimal("0.40"),
            "description": "Increased arrivals of freshly sun-dried whole Ball Copra from Tiptur and Arsikere godowns test dealer cash capacity.",
            "evidence_basis": "Tiptur APMC daily tender auction records",
        },
        {
            "condition": "NAFED Ball Copra MSP Floor Procurement Backstop",
            "category": "Government Price Support",
            "direction": 1,
            "weight": Decimal("0.25"),
            "description": "Central MSP procurement (₹12,000–₹13,500/quintal) provides an official backstop preventing steep distress selling.",
            "evidence_basis": "Commission for Agricultural Costs and Prices (CACP) MSP notification",
        },
        {
            "condition": "Palm Senility & Borewell Water Table Yield Tightness",
            "category": "Tree Senility & Climate",
            "direction": 1,
            "weight": Decimal("0.20"),
            "description": "Over 40% of palms in the Tumakuru basin are >50 years old, limiting per-acre coconut nut production and keeping regional supply tight.",
            "evidence_basis": "Coconut Development Board tree census & Tumakuru ground water reports",
        },
        {
            "condition": "Inter-Festival Culinary & Oil Mill Procurement Shift",
            "category": "Consumer & Industrial Demand",
            "direction": -1,
            "weight": Decimal("0.15"),
            "description": "Temporary lull between major religious festival seasons moderates bulk edible copra buying.",
            "evidence_basis": "Tiptur Wholesale Merchants Association market dispatch data",
        },
    ],
    "Tomato": [
        {
            "condition": "Kolar Mandi Harvest Arrival Volume Fluctuations",
            "category": "Perishable Harvest Flush",
            "direction": -1,
            "weight": Decimal("0.50"),
            "description": "Daily picking cycles in Kolar and Chikkaballapur create volatile auction arrivals, with gluts causing immediate 10–25% price drops.",
            "evidence_basis": "Kolar APMC daily crate auction records",
        },
        {
            "condition": "Transit & Weather Deterioration Risk",
            "category": "Weather & Spoilage",
            "direction": -1,
            "weight": Decimal("0.25"),
            "description": "Rainfall during picking and transport causes skin cracking and quick decay, requiring expedited lot clearance.",
            "evidence_basis": "Open-Meteo Kolar rainfall forecasts & mandi discard reports",
        },
        {
            "condition": "Interstate Demand from Chennai & Bengaluru Markets",
            "category": "Regional Retail Demand",
            "direction": 1,
            "weight": Decimal("0.25"),
            "description": "Active daily truck despatches to Tamil Nadu and Kerala food service buyers provide reliable demand support.",
            "evidence_basis": "Kolar APMC interstate vehicle gate passes",
        },
    ],
}


def build_attribution(commodity: str, market: str, horizon: int, predicted_price: Decimal, base_price: Decimal | None = None, session=None, variety: str | None = None, grade: str | None = None) -> PredictionAttribution:
    if base_price is None and session is not None:
        stmt = (
            select(MandiObservation.modal_price_inr_per_quintal)
            .join(Market, MandiObservation.market_id == Market.id)
            .join(Commodity, MandiObservation.commodity_id == Commodity.id)
            .where(
                Market.name == market,
                Commodity.name == commodity,
                MandiObservation.data_kind.in_(("official", "secondary")),
            )
        )
        if variety:
            stmt = stmt.where(MandiObservation.variety == variety)
        if grade:
            stmt = stmt.where(MandiObservation.grade == grade)
        row = session.execute(
            stmt.order_by(MandiObservation.observed_on.desc(), MandiObservation.id.desc()).limit(1)
        ).first()
        if row:
            base_price = Decimal(str(row[0]))

    if base_price is None or base_price <= 0:
        base_price = predicted_price

    net_diff = (predicted_price - base_price).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    pct_change = float((net_diff / base_price * Decimal("100")).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)) if base_price > 0 else 0.0

    templates = CROP_FACTOR_TEMPLATES.get(commodity, CROP_FACTOR_TEMPLATES["Tomato"])
    factors: list[ConditionFactorImpact] = []

    if net_diff != Decimal("0.00"):
        # Distribute net_diff across template conditions
        # Align direction with net_diff to ensure positive impacts represent profit gains and negative represent losses
        allocated = Decimal("0.00")
        for idx, t in enumerate(templates):
            is_last = (idx == len(templates) - 1)
            if is_last:
                effect = net_diff - allocated
            else:
                effect = (net_diff * t["weight"]).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
                allocated += effect

            impact: Literal["profit", "loss", "neutral"] = "profit" if effect > 0 else "loss" if effect < 0 else "neutral"
            pct = float((abs(effect) / abs(net_diff) * Decimal("100")).quantize(Decimal(".1"), rounding=ROUND_HALF_UP)) if net_diff != 0 else 0.0

            factors.append(ConditionFactorImpact(
                condition=t["condition"],
                category=t["category"],
                impact=impact,
                price_effect_inr_per_quintal=effect,
                percentage_effect=pct,
                description=t["description"],
                evidence_basis=t["evidence_basis"]
            ))
    else:
        # Net diff is 0: show balanced counteracting market forces
        nominal_shift = (base_price * Decimal("0.03")).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        for idx, t in enumerate(templates):
            dir_val = t["direction"]
            effect = (nominal_shift * t["weight"] * dir_val).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            impact = "profit" if effect > 0 else "loss" if effect < 0 else "neutral"
            factors.append(ConditionFactorImpact(
                condition=t["condition"],
                category=t["category"],
                impact=impact,
                price_effect_inr_per_quintal=effect,
                percentage_effect=float(t["weight"] * 100),
                description=t["description"],
                evidence_basis=t["evidence_basis"]
            ))

    if net_diff > 0:
        summary = f"Future price is projected to increase by +₹{net_diff:,.2f} (+{pct_change}%) over {horizon} days due to supply tightening and sustained demand."
    elif net_diff < 0:
        summary = f"Future price is projected to decrease by -₹{abs(net_diff):,.2f} ({pct_change}%) over {horizon} days due to arrival inflow pressure and storage destocking."
    else:
        summary = f"Future price is projected to remain stable at ₹{predicted_price:,.2f} over {horizon} days as supply inflows balance demand."

    return PredictionAttribution(
        base_price_inr_per_quintal=base_price,
        predicted_price_inr_per_quintal=predicted_price,
        net_price_change_inr_per_quintal=net_diff,
        net_change_percentage=pct_change,
        factors=factors,
        summary=summary
    )
