"""Dashboard analytics API — per-condominium KPIs for a given month."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_operator
from app.models.billing import Billing, BillingItem, BillingStatus
from app.models.condominium import Condominium, OperatorAssignment
from app.models.unit import Resident, Unit
from app.models.user import User, UserRole

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class TopUnit(BaseModel):
    unit_code: str
    resident_name: Optional[str] = None
    total_amount: float
    total_qty: int


class Defaulter(BaseModel):
    unit_code: str
    resident_name: Optional[str] = None
    total_amount: float
    days_overdue: int
    status: str   # "open" | "submitted"


class TrendPoint(BaseModel):
    reference_month: str
    total_billed: float
    total_collected: float
    total_open: float
    default_rate: float


class TrendResponse(BaseModel):
    condominium_id: int
    points: list[TrendPoint]


class DashboardResponse(BaseModel):
    condominium_id: int
    condominium_name: str
    reference_month: str
    total_billed: float
    total_collected: float
    total_open: float
    qty_billed: int
    qty_paid: int
    qty_open: int
    qty_submitted: int
    qty_no_consumption: int
    qty_draft: int
    default_rate: float   # percent
    has_submitted_waiting: bool
    top5: list[TopUnit]
    defaulters: list[Defaulter]


@router.get("/{condominium_id}/{reference_month}", response_model=DashboardResponse)
async def get_dashboard(
    condominium_id: int,
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Condomínio não encontrado")

    # Authorization: operator can only see assigned condominiums
    if current_user.role == UserRole.operator:
        asgn = await db.execute(
            select(OperatorAssignment).where(
                OperatorAssignment.condominium_id == condominium_id,
                OperatorAssignment.user_id == current_user.id,
            )
        )
        if not asgn.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    # Get all units for this condominium
    units_result = await db.execute(
        select(Unit).where(Unit.condominium_id == condominium_id, Unit.is_active.is_(True))
    )
    units = units_result.scalars().all()
    unit_ids = [u.id for u in units]
    unit_by_id = {u.id: u for u in units}

    if not unit_ids:
        return DashboardResponse(
            condominium_id=condominium_id,
            condominium_name=condo.name,
            reference_month=reference_month,
            total_billed=0, total_collected=0, total_open=0,
            qty_billed=0, qty_paid=0, qty_open=0, qty_submitted=0,
            qty_no_consumption=0, qty_draft=0,
            default_rate=0, has_submitted_waiting=False, top5=[], defaulters=[],
        )

    # Fetch billings for the month
    billings_result = await db.execute(
        select(Billing).where(
            Billing.unit_id.in_(unit_ids),
            Billing.reference_month == reference_month,
            Billing.is_legacy.is_(False),
        )
    )
    billings = billings_result.scalars().all()

    # Aggregate per-billing quantities from billing items
    billing_qtys: dict[int, int] = {}
    if billings:
        billing_ids = [b.id for b in billings]
        items_result = await db.execute(
            select(BillingItem).where(BillingItem.billing_id.in_(billing_ids))
        )
        for item in items_result.scalars().all():
            billing_qtys[item.billing_id] = billing_qtys.get(item.billing_id, 0) + item.quantity

    # Get residents for unit mapping
    residents_result = await db.execute(
        select(Resident).where(Resident.unit_id.in_(unit_ids), Resident.is_current.is_(True))
    )
    resident_by_unit: dict[int, str] = {}
    for r in residents_result.scalars().all():
        resident_by_unit[r.unit_id] = r.name or ""

    # Compute KPIs
    total_billed = 0.0
    total_collected = 0.0
    total_open = 0.0
    qty_paid = 0
    qty_open = 0
    qty_submitted = 0
    qty_no_consumption = 0
    qty_draft = 0

    top_candidates: list[TopUnit] = []
    defaulters: list[Defaulter] = []

    for b in billings:
        unit = unit_by_id.get(b.unit_id)
        unit_code = unit.unit_code if unit else "?"
        resident_name = resident_by_unit.get(b.unit_id)
        amount = float(b.total_amount)
        qty = billing_qtys.get(b.id, 0)

        if b.status != BillingStatus.draft:
            total_billed += amount

        if b.status == BillingStatus.paid:
            total_collected += amount
            qty_paid += 1
        elif b.status == BillingStatus.open:
            total_open += amount
            qty_open += 1
            defaulters.append(Defaulter(
                unit_code=unit_code,
                resident_name=resident_name,
                total_amount=amount,
                days_overdue=b.days_overdue or 0,
                status="open",
            ))
        elif b.status == BillingStatus.submitted:
            total_open += amount
            qty_submitted += 1
            defaulters.append(Defaulter(
                unit_code=unit_code,
                resident_name=resident_name,
                total_amount=amount,
                days_overdue=0,
                status="submitted",
            ))
        elif b.status == BillingStatus.no_consumption:
            qty_no_consumption += 1
        elif b.status in (BillingStatus.draft, BillingStatus.pending_submission):
            qty_draft += 1

        if b.status != BillingStatus.draft and amount > 0:
            top_candidates.append(TopUnit(
                unit_code=unit_code,
                resident_name=resident_name,
                total_amount=amount,
                total_qty=qty,
            ))

    qty_billed = qty_paid + qty_open + qty_submitted + qty_no_consumption
    default_rate = round((qty_open / qty_billed * 100), 1) if qty_billed > 0 else 0.0

    top5 = sorted(top_candidates, key=lambda x: x.total_amount, reverse=True)[:5]
    defaulters_sorted = sorted(defaulters, key=lambda x: x.days_overdue, reverse=True)

    return DashboardResponse(
        condominium_id=condominium_id,
        condominium_name=condo.name,
        reference_month=reference_month,
        total_billed=round(total_billed, 2),
        total_collected=round(total_collected, 2),
        total_open=round(total_open, 2),
        qty_billed=qty_billed,
        qty_paid=qty_paid,
        qty_open=qty_open,
        qty_submitted=qty_submitted,
        qty_no_consumption=qty_no_consumption,
        qty_draft=qty_draft,
        default_rate=default_rate,
        has_submitted_waiting=qty_submitted > 0,
        top5=top5,
        defaulters=defaulters_sorted,
    )


# ── GET /trend/{condominium_id} ──────────────────────────────────────


@router.get("/trend/{condominium_id}", response_model=TrendResponse)
async def get_trend(
    condominium_id: int,
    months: int = Query(default=6, ge=2, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Return billing trend for the last N months (oldest → newest)."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Condomínio não encontrado")

    if current_user.role == UserRole.operator:
        asgn = await db.execute(
            select(OperatorAssignment).where(
                OperatorAssignment.condominium_id == condominium_id,
                OperatorAssignment.user_id == current_user.id,
            )
        )
        if not asgn.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    # Build the list of months to include (oldest first)
    now = datetime.now()
    target_months: list[str] = []
    for i in range(months - 1, -1, -1):
        y = now.year
        m = now.month - i
        while m <= 0:
            m += 12
            y -= 1
        target_months.append(f"{y}-{m:02d}")

    # Get unit ids for this condo
    units_result = await db.execute(
        select(Unit.id).where(Unit.condominium_id == condominium_id, Unit.is_active.is_(True))
    )
    unit_ids = list(units_result.scalars().all())

    if not unit_ids:
        return TrendResponse(
            condominium_id=condominium_id,
            points=[TrendPoint(reference_month=m, total_billed=0, total_collected=0, total_open=0, default_rate=0) for m in target_months],
        )

    # Fetch all billings for those months
    billings_result = await db.execute(
        select(Billing).where(
            Billing.unit_id.in_(unit_ids),
            Billing.reference_month.in_(target_months),
            Billing.is_legacy.is_(False),
        )
    )
    billings = billings_result.scalars().all()

    # Group by month
    by_month: dict[str, list[Billing]] = {m: [] for m in target_months}
    for b in billings:
        if b.reference_month in by_month:
            by_month[b.reference_month].append(b)

    points: list[TrendPoint] = []
    for month in target_months:
        total_billed = 0.0
        total_collected = 0.0
        total_open = 0.0
        qty_billed = 0
        qty_open = 0

        for b in by_month[month]:
            amount = float(b.total_amount)
            if b.status != BillingStatus.draft:
                total_billed += amount
                qty_billed += 1
            if b.status == BillingStatus.paid:
                total_collected += amount
            elif b.status in (BillingStatus.open, BillingStatus.submitted):
                total_open += amount
                if b.status == BillingStatus.open:
                    qty_open += 1

        default_rate = round((qty_open / qty_billed * 100), 1) if qty_billed > 0 else 0.0
        points.append(TrendPoint(
            reference_month=month,
            total_billed=round(total_billed, 2),
            total_collected=round(total_collected, 2),
            total_open=round(total_open, 2),
            default_rate=default_rate,
        ))

    return TrendResponse(condominium_id=condominium_id, points=points)
