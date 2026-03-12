import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PriceSource(str, enum.Enum):
    local = "local"
    erp = "erp"


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity_liters: Mapped[int] = mapped_column(Integer, nullable=False)
    erp_product_code: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProductPrice(Base):
    __tablename__ = "product_price"
    __table_args__ = (
        UniqueConstraint("product_id", "condominium_id", "valid_from", name="uq_product_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    condominium_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("condominium.id", ondelete="CASCADE"), index=True
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    source: Mapped[PriceSource] = mapped_column(
        Enum(PriceSource, name="pricesource"),
        nullable=False,
        default=PriceSource.erp,
    )
