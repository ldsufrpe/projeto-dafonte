"""Pydantic schemas for Stock API responses and requests."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Response schemas ────────────────────────────────────────────────


class StockEntryResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    reference_month: str
    quantity: int
    entry_type: str
    notes: Optional[str]
    created_at: datetime


class ProductStockOverview(BaseModel):
    product_id: int
    product_name: str
    capacity_liters: int
    saldo_anterior: int
    entradas: int
    consumo_lancado: int
    saldo_atual: int
    is_negative: bool
    min_stock_alert: Optional[int] = None
    is_below_threshold: bool = False


class StockOverviewResponse(BaseModel):
    condominium_id: int
    condominium_name: str
    reference_month: str
    products: list[ProductStockOverview]
    entries: list[StockEntryResponse]


class StockChartResponse(BaseModel):
    months: list[str]
    series: dict[str, list[int]]  # product_name → saldo_atual per month


# ── Request schemas ─────────────────────────────────────────────────


class CreateStockEntryRequest(BaseModel):
    condominium_id: int
    product_id: int
    reference_month: str  # YYYY-MM
    quantity: int = Field(gt=0)
    entry_type: str = "purchase"  # purchase | initial
    notes: Optional[str] = None


class UpdateStockEntryRequest(BaseModel):
    quantity: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = None
