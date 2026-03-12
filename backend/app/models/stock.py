import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
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
