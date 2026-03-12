"""Pydantic schemas for ERP data contracts.

These schemas define the interface between FonteGest and the ERP system
(Retaguarda DataSnap). Both MockERPClient and future DataSnapClient
return/accept these exact types.
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


# ── Inbound (ERP → FonteGest) ──────────────────────────────────────


class UserSyncSchema(BaseModel):
    username: str
    password: str  # cleartext from ERP — FonteGest hashes with bcrypt
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_admin: bool = False


class CondominiumSyncSchema(BaseModel):
    erp_code: str
    name: str
    address: Optional[str] = None
    prices: dict[str, Optional[str]]  # {"INDAIA20LT": "13.80", "IAIA20L": null}


class ProductSchema(BaseModel):
    erp_product_code: str
    name: str
    capacity_liters: int
    unit_price: Decimal


class ResidentSchema(BaseModel):
    unit_code: str
    resident_name: str
    cpf_masked: str = ""
    is_current: bool = True


class PaymentStatusSchema(BaseModel):
    unit_code: str
    status: str  # "paid" | "open" | "no_consumption"
    erp_invoice_id: Optional[str] = None
    days_overdue: int = 0


# ── Outbound (FonteGest → ERP) ─────────────────────────────────────


class BillingItemPayload(BaseModel):
    unit_code: str
    erp_product_code: str
    quantity: int
    unit_price: str  # decimal as string


class BillingPayloadSchema(BaseModel):
    erp_code: str
    reference_month: str  # YYYY-MM
    items: list[BillingItemPayload]


# ── Response ────────────────────────────────────────────────────────


class SubmitResultItem(BaseModel):
    unit_code: str
    erp_invoice_id: Optional[str] = None
    success: bool
    error: Optional[str] = None


class SubmitResultSchema(BaseModel):
    success: bool
    submitted_count: int
    skipped_count: int
    results: list[SubmitResultItem]
