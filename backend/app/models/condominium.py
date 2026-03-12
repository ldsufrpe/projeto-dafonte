import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CommissionType(str, enum.Enum):
    fixed = "fixed"
    percent = "percent"
    per_unit = "per_unit"


class Condominium(Base):
    __tablename__ = "condominium"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    erp_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    commission_type: Mapped[CommissionType] = mapped_column(
        Enum(CommissionType, name="commissiontype"),
        nullable=False,
        default=CommissionType.fixed,
    )
    commission_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    go_live_date: Mapped[Optional[date]] = mapped_column(Date)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OperatorAssignment(Base):
    __tablename__ = "operator_assignment"
    __table_args__ = (
        UniqueConstraint("user_id", "condominium_id", name="uq_operator_assignment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    condominium_id: Mapped[int] = mapped_column(
        ForeignKey("condominium.id", ondelete="CASCADE"), nullable=False, index=True
    )


class CommissionRate(Base):
    __tablename__ = "commission_rate"
    __table_args__ = (
        UniqueConstraint(
            "condominium_id", "product_id", "valid_from", name="uq_commission_rate"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    condominium_id: Mapped[int] = mapped_column(
        ForeignKey("condominium.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    value_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
