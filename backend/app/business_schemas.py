from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.sale_schemas import Input

BusinessType = Literal['PRIVATE_MANDI', 'PRIVATE_BUYER']
VerificationState = Literal['PENDING_VERIFICATION', 'VERIFIED', 'REJECTED', 'SUSPENDED']
BusinessRoleName = Literal['PRIVATE_MANDI_OWNER', 'PRIVATE_BUYER', 'MANDI_STAFF']


class BusinessRegistration(Input):
    business_type: BusinessType
    name: str = Field(min_length=2, max_length=200)
    contact_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r'^\+[1-9]\d{7,14}$')
    email: str = Field(max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    address: str = Field(min_length=5, max_length=1000)
    district: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=120)
    registration_details: str = Field(min_length=3, max_length=2000)
    verification_information: str = Field(min_length=3, max_length=2000)
    document_references: list[str] = Field(default_factory=list, max_length=10)
    commodity_ids: list[int] = Field(min_length=1, max_length=100)
    operating_hours: str | None = Field(default=None, max_length=500)
    buyer_type: Literal['INDIVIDUAL_TRADER', 'AGRICULTURAL_BUSINESS', 'PROCUREMENT_COMPANY', 'REGISTERED_BUYER'] | None = None

    @field_validator('document_references')
    @classmethod
    def reference_length(cls, values):
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError('Document references must contain 1–500 characters')
        return values

    @model_validator(mode='after')
    def distinct_business_type(self):
        if self.business_type == 'PRIVATE_MANDI' and (not self.operating_hours or self.buyer_type):
            raise ValueError('Private mandis require operating hours and cannot use a buyer subtype')
        if self.business_type == 'PRIVATE_BUYER' and (not self.buyer_type or self.operating_hours):
            raise ValueError('Private buyers require a buyer type and cannot use mandi operating hours')
        if len(set(self.commodity_ids)) != len(self.commodity_ids) or any(i <= 0 for i in self.commodity_ids):
            raise ValueError('Choose distinct registered crop IDs')
        return self


class WorkspaceSelection(Input):
    mode: Literal['FARMER', 'BUSINESS']
    business_id: int | None = Field(default=None, gt=0)
    role: BusinessRoleName | None = None


class BusinessReview(Input):
    version: int = Field(ge=1)
    state: VerificationState
    evidence: str = Field(min_length=10, max_length=2000)
    contact_verified: bool = False
    registration_checked: bool = False
    documents_required: bool = False


class BusinessMemberInput(Input):
    user_id: int = Field(gt=0)
    role: BusinessRoleName
    can_manage: bool = False
    active: bool = True


class MarketAssignmentInput(Input):
    private_mandi_id: int = Field(gt=0)


class BusinessProfileResponse(BaseModel):
    id: int
    business_type: BusinessType
    name: str
    contact_name: str
    phone: str
    email: str
    address: str
    district: str
    state: str
    registration_details: str
    verification_information: str
    document_references: list[str]
    verification_state: VerificationState
    created_by: int
    version: int
    created_at: datetime
    commodity_ids: list[int]
    authorized_roles: list[str]
    can_publish: bool
    is_apmc: Literal[False]
    public_offers_implemented: Literal[True]
    private_mandi_id: int | None
    assigned_private_mandi_id: int | None
    operating_hours: str | None
    buyer_type: str | None


class WorkspaceChoice(BaseModel):
    business_id: int
    name: str
    business_type: BusinessType
    role: BusinessRoleName


class ActiveWorkspace(BaseModel):
    mode: Literal['FARMER', 'BUSINESS']
    business_id: int | None
    role: BusinessRoleName | None
    name: str | None = None
    business_type: BusinessType | None = None


class BusinessAccessResponse(BaseModel):
    user_id: int
    roles: list[str]
    workspaces: list[WorkspaceChoice]
    active_workspace: ActiveWorkspace
