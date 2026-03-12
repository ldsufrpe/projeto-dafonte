import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BillingStatus(str, enum.Enum):
    draft = "draft"
    pending_submission = "pending_submission"
    submitted = "submitted"
    open = "open"
    paid = "paid"
    no_consumption = "no_consumption"


class Billing(Base):
    __tablename__ = "billing"
    __table_args__ = (
        UniqueConstraint("unit_id", "reference_month", name="uq_billing"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    resident_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("resident.id", ondelete="SET NULL"), index=True
    )
    reference_month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    status: Mapped[BillingStatus] = mapped_column(
        Enum(BillingStatus, name="billingstatus"),
        nullable=False,
        default=BillingStatus.draft,
    )
    days_overdue: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    erp_invoice_id: Mapped[Optional[str]] = mapped_column(String(100))
    resident_changed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_legacy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BillingItem(Base):
    __tablename__ = "billing_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    billing_id: Mapped[int] = mapped_column(
        ForeignKey("billing.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_price_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_price.id", ondelete="SET NULL")
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
