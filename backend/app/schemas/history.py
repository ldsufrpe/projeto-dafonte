"""Schemas for the history (histórico) endpoints."""

from pydantic import BaseModel


class BillingItemRow(BaseModel):
    product_name: str
    quantity: int
    unit_price: float


class BillingRow(BaseModel):
    billing_id: int
    unit_code: str
    resident_name: str | None
    status: str
    total_amount: float
    evidence_count: int
    items: list[BillingItemRow]


class MonthSummary(BaseModel):
    reference_month: str  # "2026-03"
    total_billed: float
    total_received: float
    total_units: int
    qty_per_product: dict[str, int]  # product_name → total qty
    status_counts: dict[str, int]  # status → count
    is_current: bool  # True if this is the current month


class MonthDetail(BaseModel):
    summary: MonthSummary
    billings: list[BillingRow]
