from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CommissionResult(BaseModel):
    condominium_id: int
    condominium_name: str
    reference_month: str
    commission_type: str
    commission_value: Optional[Decimal]
    total_received: Decimal
    commission_due: Decimal


class OperatorPerformanceItem(BaseModel):
    condominium_id: int
    condominium_name: str
    total_billed: Decimal
    total_received: Decimal
    success_rate: Decimal
    commission_due: Decimal


class CommissionConfigUpdate(BaseModel):
    commission_type: str  # "fixed" | "percent" | "per_unit"
    commission_value: Optional[Decimal] = None


class CommissionRateCreate(BaseModel):
    product_id: int
    value_per_unit: Decimal
    valid_from: date


class CommissionRateOut(BaseModel):
    id: int
    condominium_id: int
    product_id: int
    product_name: Optional[str] = None
    value_per_unit: Decimal
    valid_from: date

    model_config = {"from_attributes": True}
