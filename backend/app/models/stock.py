import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StockEntryType(str, enum.Enum):
    purchase = "purchase"
    initial = "initial"


class StockEntry(Base):
    __tablename__ = "stock_entry"
    __table_args__ = (
        Index("ix_stock_entry_condo_month", "condominium_id", "reference_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    condominium_id: Mapped[int] = mapped_column(
        ForeignKey("condominium.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reference_month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_type: Mapped[StockEntryType] = mapped_column(
        Enum(StockEntryType, name="stockentrytype"), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StockAlertThreshold(Base):
    """Minimum stock threshold per condominium, optionally per product.
    product_id=NULL means a global threshold for the condominium.
    product_id=X means a product-specific threshold (takes priority over global).
    """
    __tablename__ = "stock_alert_threshold"
    __table_args__ = (
        UniqueConstraint("condominium_id", "product_id", name="uq_stock_alert_threshold"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    condominium_id: Mapped[int] = mapped_column(
        ForeignKey("condominium.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    min_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
