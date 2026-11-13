from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.sale_schemas import Input, Price, Quantity


class OfferTerms(Input):
    commodity_id: int = Field(gt=0)
    variety: str = Field(min_length=1, max_length=120)
    grade: str = Field(min_length=1, max_length=120)
    crop_condition: str = Field(min_length=1, max_length=500)
    quality_standards: str = Field(min_length=1, max_length=2000)
    image_references: list[str] = Field(default_factory=list, max_length=5)
    total_quantity: Quantity
    unit: Literal["quintal"] = "quintal"
    minimum_quantity: Quantity
    maximum_quantity: Quantity
    daily_intake: Quantity | None = None
    offered_price: Price
    price_kind: Literal["FIRM", "INDICATIVE", "NEGOTIABLE"]
    minimum_price: Price | None = None
    maximum_price: Price | None = None
    price_basis: str = Field(min_length=1, max_length=500)
    price_valid_until: AwareDatetime
    purchasing_centre: str = Field(min_length=2, max_length=200)
    address: str = Field(min_length=5, max_length=1000)
    district: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=120)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=10, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=10, decimal_places=6)
    service_area: str = Field(min_length=1, max_length=1000)
    transport: Literal["FARMER_DELIVERY", "BUSINESS_PICKUP"]
    pickup_charge: Decimal | None = Field(default=None, ge=0, le=10000000, decimal_places=2)
    unloading_charge: Decimal | None = Field(default=None, ge=0, le=10000000, decimal_places=2)
    charge_basis: Literal["INR_PER_QUINTAL", "INR_PER_TRIP"]
    weighment: str = Field(min_length=1, max_length=1000)
    arrival_dates: list[date] = Field(min_length=1, max_length=100)
    appointment_required: bool = True
    payment_methods: list[str] = Field(min_length=1, max_length=10)
    payment_timing: str = Field(min_length=1, max_length=500)
    payment_terms: str = Field(min_length=1, max_length=2000)
    known_deductions: str = Field(min_length=1, max_length=1000)
    instructions: str = Field(default="", max_length=2000)
    contact_availability: str = Field(min_length=1, max_length=500)
    special_requirements: str = Field(default="", max_length=1000)
    starts_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def consistency(self):
        if not self.minimum_quantity <= self.maximum_quantity <= self.total_quantity:
            raise ValueError("Quantity limits must satisfy minimum <= maximum <= total")
        if self.daily_intake and self.daily_intake < self.minimum_quantity:
            raise ValueError("Daily intake cannot be smaller than minimum lot")
        if not self.starts_at < self.expires_at or not self.starts_at < self.price_valid_until <= self.expires_at:
            raise ValueError("Start must precede price validity and expiry")
        if self.minimum_price and (self.price_kind != "NEGOTIABLE" or self.minimum_price > self.offered_price):
            raise ValueError("Minimum price requires a negotiable offer and cannot exceed the quote")
        if self.maximum_price and self.maximum_price < self.offered_price:
            raise ValueError("Maximum price cannot be below the quote")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Supply both map coordinates or neither")
        if len(set(self.arrival_dates)) != len(self.arrival_dates):
            raise ValueError("Arrival dates must be distinct")
        # Arrival dates use Karnataka local dates, never UTC calendar boundaries.
        from zoneinfo import ZoneInfo

        start = self.starts_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
        end = self.expires_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
        if any(not start <= d <= end for d in self.arrival_dates):
            raise ValueError("Arrival dates must lie within offer validity")
        if any(not s.strip() or len(s) > 500 for s in self.image_references + self.payment_methods):
            raise ValueError("Image references/payment methods must have 1–500 characters")
        return self


class OfferCreate(OfferTerms):
    business_id: int = Field(gt=0)


class OfferUpdate(OfferTerms):
    version: int = Field(ge=1)


class VersionInput(Input):
    version: int = Field(ge=1)


class FarmerRequestInput(Input):
    offer_version: int = Field(ge=1)
    available_quantity: Quantity
    quantity: Quantity
    expected_price: Price
    variety: str = Field(min_length=1, max_length=120)
    grade: str = Field(min_length=1, max_length=120)
    arrival_at: AwareDatetime
    message: str = Field(default="", max_length=2000)
    contact_consent: bool = False
    quality_confirmed: Literal[True]
    terms_confirmed: Literal[True]

    @model_validator(mode="after")
    def harvest(self):
        if self.quantity > self.available_quantity:
            raise ValueError("Requested quantity exceeds available harvest")
        return self


class ResponseInput(Input):
    version: int = Field(ge=1)
    quantity: Quantity
    price: Price
    arrival_at: AwareDatetime
    expires_at: AwareDatetime
    payment_terms: str = Field(min_length=1, max_length=2000)
    message: str = Field(default="", max_length=2000)


class RejectInput(VersionInput):
    reason: str = Field(default="", max_length=1000)


class PurchaseOfferView(Input):
    id: int
    commodity_name: str
    business_id: int
    version: int
    status: str
    terms: OfferTerms
    quantity_required: str
    quantity_reserved: str
    quantity_committed: str
    quantity_remaining: str
    unit: Literal["quintal"]
    currency: Literal["INR"]
    price_updated_at: AwareDatetime
    created_at: AwareDatetime
    request_count: int
    price_history: list[dict] | None = None
    history: list[dict] | None = None
