from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, le=100000000, max_digits=11, decimal_places=2)]
Price = Annotated[Decimal, Field(gt=0, le=10000000, max_digits=10, decimal_places=2)]
Quantity = Annotated[Decimal, Field(gt=0, le=100000, max_digits=9, decimal_places=3)]
Text = Annotated[str, Field(max_length=2000)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Login(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('email')
    @classmethod
    def email_format(cls, value):
        if '@' not in value or any(c.isspace() for c in value):
            raise ValueError('Valid email required')
        return value.lower()


class Register(Login):
    name: str = Field(min_length=1, max_length=120)
    language: Literal['en', 'kn'] = 'en'
    invitation_token: str | None = Field(None, max_length=100)


class SaleCreate(Input):
    mandi_id: int = Field(gt=0)
    crop_id: int = Field(gt=0)
    variety: str = Field(min_length=1, max_length=120)
    grade: str = Field(min_length=1, max_length=120)
    total_harvest_quantity: Quantity
    requested_quantity: Quantity
    expected_price_per_quintal: Price
    preferred_arrival_at: datetime
    estimated_costs_inr: Money = Decimal('0')
    farmer_message: Text = ''
    contact_sharing_consent: bool = False

    @model_validator(mode='after')
    def valid_quantities(self):
        if self.requested_quantity > self.total_harvest_quantity:
            raise ValueError('Requested quantity exceeds harvest')
        if self.preferred_arrival_at.utcoffset() is None:
            raise ValueError('Arrival timestamp must include timezone')
        return self


class Versioned(Input):
    version: int = Field(ge=1)


class OfferInput(Versioned):
    quantity: Quantity
    price: Price
    arrival_at: datetime
    expires_at: datetime
    message: Text = ''

    @model_validator(mode='after')
    def aware(self):
        if self.arrival_at.utcoffset() is None or self.expires_at.utcoffset() is None:
            raise ValueError('Timestamps must include timezone')
        return self


class ConfirmInput(Versioned):
    offer_id: int = Field(gt=0)


class ReasonInput(Versioned):
    reason: Text = ''


class ArrivedInput(Versioned):
    received_quantity: Quantity


class WeighmentInput(Versioned):
    weighed_quantity: Quantity
    final_price: Price
    deductions_inr: Money
    quality: str = Field(min_length=1, max_length=1000)
    payment_status: Literal['NOT_PAID', 'PENDING', 'PARTIALLY_PAID', 'PAID', 'DISPUTED']
    payment_reference: str = Field('', max_length=255)


class PaymentInput(Versioned):
    payment_status: Literal['NOT_PAID', 'PENDING', 'PARTIALLY_PAID', 'PAID', 'DISPUTED']
    payment_reference: str = Field('', max_length=255)


class InviteInput(Input):
    email: str = Field(max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    role: Literal['MANDI_OWNER', 'MANDI_STAFF']
    market_id: int = Field(gt=0)
    identity_evidence: str = Field(min_length=10, max_length=1000)


class MandiInput(Input):
    market_id: int = Field(gt=0)
    active: bool
    registration_details: str = Field(min_length=10, max_length=1000)
    commodity_ids: list[int] = Field(min_length=1, max_length=100)


class PreferenceInput(Input):
    email: bool = False
    sms: bool = False
    whatsapp: bool = False


class TokenInput(Input):
    token: str = Field(min_length=20, max_length=100)


class StaffInput(Input):
    user_id: int = Field(gt=0)
    market_id: int = Field(gt=0)
    can_transact: bool
    active: bool = True


class OfferResponse(BaseModel):
    id: int
    request_id: int
    author_id: int
    kind: str
    quantity: Decimal
    price: Decimal
    arrival_at: datetime
    expires_at: datetime
    message: str
    created_at: datetime


class BookingResponse(BaseModel):
    id: int
    request_id: int
    offer_id: int
    arrival_at: datetime
    confirmed_by: int
    arrived_at: datetime | None
    received_quantity: Decimal | None
    created_at: datetime


class TransactionResponse(BaseModel):
    id: int
    request_id: int
    recorded_by: int
    weighed_quantity: Decimal
    final_price: Decimal
    quality: str
    gross_inr: Decimal
    deductions_inr: Decimal
    net_inr: Decimal
    payment_status: str
    payment_reference: str
    created_at: datetime


class SaleResponse(BaseModel):
    id: int
    public_request_id: str
    mandi_id: int
    crop_id: int
    mandi_name: str
    crop_name: str
    variety: str
    grade: str
    total_harvest_quantity: Decimal
    requested_quantity: Decimal
    expected_price_per_quintal: Decimal
    reference_modal_price: Decimal | None
    reference_price_observation_id: int | None
    reference_price_date: date | None = None
    preferred_arrival_at: datetime
    estimated_costs_inr: Decimal
    estimated_net_inr: Decimal
    farmer_message: str
    contact_sharing_consent: bool
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    offers: list[OfferResponse]
    booking: BookingResponse | None
    transaction: TransactionResponse | None
    farmer_phone: str | None = None
    unit: Literal['INR/quintal']
    quantity_unit: Literal['quintals']
    payment_notice: str
