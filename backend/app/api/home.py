"""Home overview API — work panel for operators and admin."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.api.finance import _calc_commission
from app.models.billing import Billing, BillingItem, BillingStatus
from app.models.condominium import Condominium, OperatorAssignment
from app.models.product import Product
from app.models.stock import StockAlertThreshold, StockEntry
from app.models.unit import Unit
from app.models.user import User, UserRole

router = APIRouter(prefix="/home", tags=["home"])


async def _has_stock_alert(db: AsyncSession, condominium_id: int, reference_month: str) -> bool:
    """Return True if any active product has saldo_atual below configured threshold.
    Priority: per-product threshold > global threshold > fallback (< 0)."""
    products_result = await db.execute(
        select(Product.id).where(Product.is_active.is_(True))
    )
    product_ids = products_result.scalars().all()
    if not product_ids:
        return False

    # Load thresholds for this condominium
    thresholds_result = await db.execute(
        select(StockAlertThreshold).where(StockAlertThreshold.condominium_id == condominium_id)
    )
    thresholds = thresholds_result.scalars().all()
    per_product_thresholds: dict[int, int] = {}
    global_threshold: int | None = None
    for t in thresholds:
        if t.product_id is None:
            global_threshold = t.min_quantity
        else:
            per_product_thresholds[t.product_id] = t.min_quantity

    for product_id in product_ids:
        # Cumulative entries up to and including this month
        q = await db.execute(
            select(func.coalesce(func.sum(StockEntry.quantity), 0)).where(
                StockEntry.condominium_id == condominium_id,
                StockEntry.product_id == product_id,
                StockEntry.reference_month <= reference_month,
            )
        )
        total_entries: int = q.scalar() or 0

        # Cumulative consumption up to and including this month
        q = await db.execute(
            select(func.coalesce(func.sum(BillingItem.quantity), 0))
            .join(Billing, BillingItem.billing_id == Billing.id)
            .join(Unit, Billing.unit_id == Unit.id)
            .where(
                Unit.condominium_id == condominium_id,
                BillingItem.product_id == product_id,
                Billing.reference_month <= reference_month,
            )
        )
        total_consumo: int = q.scalar() or 0
        saldo = total_entries - total_consumo

        # Determine threshold: per-product > global > fallback (0)
        threshold = per_product_thresholds.get(product_id, global_threshold if global_threshold is not None else 0)
        if saldo < threshold:
            return True

    return False


class CondominiumOverview(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    erp_code: str
    onboarding_complete: bool
    month_status: str  # not_started | in_progress | submitted | synced
    units_launched: int
    total_units: int
    total_billed: float
    total_received: float
    commission_due: float
    has_stock_alert: bool
    operator_name: Optional[str] = None  # admin only


class HomeOverviewResponse(BaseModel):
    reference_month: str
    condominiums: list[CondominiumOverview]
    total_billed_all: float = 0.0
    total_received_all: float = 0.0


@router.get("/overview/{reference_month}", response_model=HomeOverviewResponse)
async def get_home_overview(
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    operator_id: int | None = Query(default=None, description="Filter by operator (admin only)"),
):
    """Return overview for all accessible condominiums for the given month.
    Admin sees all condominiums with operator name. Operator sees only assigned ones."""
    if current_user.role == UserRole.admin:
        if operator_id is not None:
            # Filter to condominiums assigned to the specified operator
            condo_result = await db.execute(
                select(Condominium)
                .join(OperatorAssignment, Condominium.id == OperatorAssignment.condominium_id)
                .where(OperatorAssignment.user_id == operator_id)
            )
        else:
            condo_result = await db.execute(select(Condominium))
        condominiums = condo_result.scalars().all()
        # Map condo_id → operator name (first active operator assigned)
        asgn_result = await db.execute(
            select(OperatorAssignment, User)
            .join(User, OperatorAssignment.user_id == User.id)
            .where(User.role == UserRole.operator, User.is_active.is_(True))
        )
        operator_by_condo: dict[int, str] = {}
        for asgn, user in asgn_result.all():
            if asgn.condominium_id not in operator_by_condo:
                operator_by_condo[asgn.condominium_id] = user.full_name or user.username
    else:
        asgn_result = await db.execute(
            select(Condominium)
            .join(OperatorAssignment, Condominium.id == OperatorAssignment.condominium_id)
            .where(OperatorAssignment.user_id == current_user.id)
        )
        condominiums = asgn_result.scalars().all()
        operator_by_condo = {}

    overviews: list[CondominiumOverview] = []

    for condo in condominiums:
        units_result = await db.execute(
            select(Unit).where(Unit.condominium_id == condo.id, Unit.is_active.is_(True))
        )
        units = units_result.scalars().all()
        total_units = len(units)
        unit_ids = [u.id for u in units]

        if unit_ids:
            billings_result = await db.execute(
                select(Billing).where(
                    Billing.unit_id.in_(unit_ids),
                    Billing.reference_month == reference_month,
                    Billing.is_legacy.is_(False),
                )
            )
            billings = billings_result.scalars().all()
        else:
            billings = []

        total_billings = len(billings)
        if total_billings == 0:
            month_status = "not_started"
        else:
            statuses = {b.status for b in billings}
            final_statuses = {BillingStatus.paid, BillingStatus.open, BillingStatus.no_consumption}
            if statuses.issubset(final_statuses):
                month_status = "synced"
            elif any(s in statuses for s in (BillingStatus.draft, BillingStatus.pending_submission)):
                month_status = "in_progress"
            else:
                month_status = "submitted"

        total_billed = float(sum(
            b.total_amount for b in billings if b.status != BillingStatus.draft
        ))
        total_received = float(sum(
            b.total_amount for b in billings if b.status == BillingStatus.paid
        ))
        units_launched = sum(1 for b in billings if b.status != BillingStatus.draft)

        _, commission_due_dec = await _calc_commission(db, condo, reference_month)
        commission_due = float(commission_due_dec)

        overviews.append(
            CondominiumOverview(
                id=condo.id,
                name=condo.name,
                address=condo.address,
                erp_code=condo.erp_code,
                onboarding_complete=condo.onboarding_complete,
                month_status=month_status,
                units_launched=units_launched,
                total_units=total_units,
                total_billed=total_billed,
                total_received=total_received,
                commission_due=commission_due,
                has_stock_alert=await _has_stock_alert(db, condo.id, reference_month),
                operator_name=operator_by_condo.get(condo.id) if current_user.role == UserRole.admin else None,
            )
        )

    return HomeOverviewResponse(
        reference_month=reference_month,
        condominiums=overviews,
        total_billed_all=sum(o.total_billed for o in overviews),
        total_received_all=sum(o.total_received for o in overviews),
    )
