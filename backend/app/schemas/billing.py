"""Pydantic schemas for Billing API responses and requests."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ── Response schemas ────────────────────────────────────────────────


class ProductHeader(BaseModel):
    """Product metadata for table header."""
    id: int
    erp_product_code: str
    name: str
    capacity_liters: int
    sort_order: int
    unit_price: Decimal


class BillingItemResponse(BaseModel):
    """Single product line within a billing row."""
    id: int
    product_id: int
    erp_product_code: str
    product_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class ResidentInfo(BaseModel):
    """Resident data embedded in a billing row."""
    id: Optional[int] = None
    name: Optional[str] = None
    cpf_masked: Optional[str] = None
    phone: Optional[str] = None


class BillingRowResponse(BaseModel):
    """One unit's billing for a given month."""
    billing_id: int
    unit_id: int
    unit_code: str
    resident: ResidentInfo
    items: list[BillingItemResponse]
    total_amount: Decimal
    status: str
    days_overdue: int = 0
    erp_invoice_id: Optional[str] = None
    resident_changed: bool = False
    has_consumption: bool = False  # computed: sum(item.quantity) > 0


class BillingGridResponse(BaseModel):
    """Full billing grid for a condominium + month."""
    condominium_id: int
    condominium_name: str
    reference_month: str
    products: list[ProductHeader]
    rows: list[BillingRowResponse]
    summary: "BillingSummary"


class BillingSummary(BaseModel):
    """Aggregate totals for the grid footer/summary bar."""
    total_units: int = 0
    total_faturado: Decimal = Decimal("0")
    total_arrecadado: Decimal = Decimal("0")
    total_em_aberto: Decimal = Decimal("0")
    totals_by_product: dict[int, int] = {}  # product_id → sum(quantity)


# ── Request schemas ─────────────────────────────────────────────────


class UpdateQuantityRequest(BaseModel):
    quantity: int = Field(ge=0, description="Quantity must be >= 0")


class UpdateResidentRequest(BaseModel):
    name: Optional[str] = None
    cpf_masked: Optional[str] = None
    phone: Optional[str] = None


class GenerateMeshRequest(BaseModel):
    condominium_id: int
    unit_start: int
    unit_end: int
    reference_month: str  # YYYY-MM
