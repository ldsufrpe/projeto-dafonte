import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OnboardingStatus(str, enum.Enum):
    pending = "pending"
    done = "done"
    error = "error"


class OnboardingImport(Base):
    __tablename__ = "onboarding_import"

    id: Mapped[int] = mapped_column(primary_key=True)
    condominium_id: Mapped[int] = mapped_column(
        ForeignKey("condominium.id", ondelete="CASCADE"), nullable=False, index=True
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[OnboardingStatus] = mapped_column(
        Enum(OnboardingStatus, name="onboardingstatus"),
        nullable=False,
        default=OnboardingStatus.pending,
    )
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_log: Mapped[Optional[dict]] = mapped_column(JSON)


class LegacyDebt(Base):
    __tablename__ = "legacy_debt"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("unit.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reference_month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
