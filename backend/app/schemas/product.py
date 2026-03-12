from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ProductUpdate(BaseModel):
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    id: int
    name: str
    capacity_liters: int
    erp_product_code: Optional[str]
    is_active: bool
    sort_order: int
    current_price: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class ProductPriceCreate(BaseModel):
    condominium_id: Optional[int] = None
    valid_from: date
    unit_price: Decimal


class ProductPriceOut(BaseModel):
    id: int
    product_id: int
    condominium_id: Optional[int]
    valid_from: date
    unit_price: Decimal
    source: str

    model_config = {"from_attributes": True}
