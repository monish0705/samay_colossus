from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ingestion import commodity_name, label, market_name
from app.reliability import ReliabilityForecast
from app.selling import HoldingOption, Name, Nonnegative, SellingRequest


class ApiError(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ApiError


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, json_schema_extra={"description": "EXAMPLE ONLY request schema; no model or live price availability is implied.", "examples": [{"market": "Kolar APMC", "commodity": "Tomato", "variety": "local", "grade": "faq", "horizon": 3}]})
    market: str = "Kolar APMC"
    commodity: str = "Tomato"
    variety: Name
    grade: Name
    horizon: Literal[1, 3, 7]
    origin_date: date | None = None

    @field_validator("horizon", mode="before")
    @classmethod
    def strict_horizon(cls, value):
        if type(value) is not int:
            raise ValueError("horizon must be an integer: 1, 3 or 7")
        return value

    @field_validator("market")
    @classmethod
    def normalize_market(cls, value):
        return market_name(value)

    @field_validator("commodity")
    @classmethod
    def normalize_commodity(cls, value):
        return commodity_name(value)

    @field_validator("variety", "grade")
    @classmethod
    def names(cls, value):
        return label(value)


class ApiInterval(BaseModel):
    nominal_level: Decimal
    lower_inr_per_quintal: Decimal
    upper_inr_per_quintal: Decimal


class PredictionResponse(ReliabilityForecast):
    prediction_inr_per_quintal: Decimal | None = None
    intervals: list[ApiInterval] = Field(default_factory=list)
    request_id: str
    price_unit: str = "INR/quintal"


class RecommendationHolding(HoldingOption):
    # Clients cannot submit trusted scenarios, reliability status or artifact paths.
    scenarios: None = None
    realization_multiplier: Decimal = Field(gt=0, le=2, allow_inf_nan=False, decimal_places=6)
    price_basis_assumption: Name
    adverse_inr_per_quintal: Nonnegative
    adverse_assumption: Name


class RecommendRequest(SellingRequest):
    holding_options: tuple[RecommendationHolding, ...] = ()

    @model_validator(mode="after")
    def supported(self):
        if self.market != market_name(self.market) or self.commodity != commodity_name(self.commodity):
            raise ValueError("Use canonical Kolar APMC / Tomato scope")
        if self.variety != label(self.variety) or self.grade != label(self.grade):
            raise ValueError("Use normalized variety and grade")
        return self


class SaleLedger(BaseModel):
    gross_inr: Decimal
    commission_inr: Decimal
    market_fee_inr: Decimal
    transport_inr: Decimal
    handling_inr: Decimal
    fixed_transaction_inr: Decimal
    net_inr: Decimal


class SellingPlan(BaseModel):
    sell_today_quintals: Decimal
    hold_initial_quintals: Decimal
    holding_days: int
    later_saleable_quintals: Decimal
    deterioration_loss_quintals: Decimal
    rounding_discard_quintals: Decimal
    storage_cost_inr: Decimal
    storage_paid_today_inr: Decimal
    storage_paid_later_inr: Decimal
    today_sale: SaleLedger
    cash_today_inr: Decimal
    cash_surplus_inr: Decimal
    later_sales: dict[str, SaleLedger]
    central_later_net_after_storage_inr: Decimal
    total_net_inr: dict[str, Decimal]
    downside_total_net_inr: Decimal
    difference_vs_sell_all_now_inr: dict[str, Decimal]
    risk_adjusted_objective_inr: Decimal
    recommendation_eligible: bool
    warnings: list[str]
    break_even_future_price_inr_per_quintal: Decimal | None
    assumptions: dict


class SellAllComparison(BaseModel):
    sale: SaleLedger
    meets_minimum_lot: bool
    meets_cash_requirement: bool


class OptimizationResponse(BaseModel):
    schema_version: str
    status: str
    recommendation_basis: str
    has_unreliable_or_missing_scenarios: bool
    decision_at: datetime
    scope: dict[str, str]
    units: dict[str, str]
    sell_all_now: SellAllComparison
    maximum_today_net_cash_upper_bound_inr: Decimal
    cash_requirement_achievable_on_grid: bool
    recommended_plan: SellingPlan | None
    best_scenario_only_or_validated_plan: SellingPlan | None
    feasible_plans: list[SellingPlan]
    rejected_counts: dict[str, int]
    risk_tolerance: str
    request_and_assumptions: dict
    explanations: list[str]


class Freshness(BaseModel):
    report_date: date | None = None
    fetched_at: datetime | None = None
    source: str | None = None
    source_url: str | None = None
    file_sha256: str | None = None
    stale: bool = True
    data_kind: str = "official"


class RecommendationResponse(BaseModel):
    request_id: str
    history_id: int
    market_data: Freshness
    predictions: list[PredictionResponse]
    reliability_warnings: list[str]
    optimization: OptimizationResponse


class ModelStatusItem(BaseModel):
    market: str
    commodity: str
    variety: str
    grade: str
    horizon: int
    model_version: str | None
    status: str
    trained_before: datetime | None = None
    dataset_fingerprint: str | None = None
    reliability_evidence_configured: bool = False
    validation_metrics: dict[str, float | int | None] | None = None
    final_holdout_metrics: dict[str, float | int | None] | None = None


class ResearchHorizon(BaseModel):
    horizon: int
    selected_model: str | None
    train_n: int
    validation_n: int
    final_n: int
    final_metrics: dict[str, float | int | None] | None = None
    naive_metrics: dict[str, float | int | None] | None = None


class ResearchStudy(BaseModel):
    version: str
    research_only: bool = True
    market: str
    commodity: str
    variety: str
    grade: str
    train_start: date
    train_end: date
    validation_end: date
    test_end: date
    limitations: str
    source_fingerprint: str
    horizons: list[ResearchHorizon]


class ModelsStatus(BaseModel):
    status: str
    models: list[ModelStatusItem]
    research_studies: list[ResearchStudy] = []


class DataStatus(BaseModel):
    historical_demo_date: date | None = None
    status: str
    official_observations: int
    fixture_observations: int
    demo_observations: int
    latest_official_report_date: date | None
    latest_official_fetched_at: datetime | None
    note: str = "Official means operator-attested government provenance, not independent publisher authentication. Fixtures/demos are never substituted as live observations."
