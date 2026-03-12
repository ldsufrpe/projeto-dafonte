"""History endpoints — consulta de meses anteriores por condomínio."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin, require_operator
from app.models.billing import Billing, BillingItem, BillingStatus
from app.models.condominium import Condominium, OperatorAssignment
from app.models.evidence import Evidence
from app.models.product import Product
from app.models.unit import Resident, Unit
from app.models.user import User, UserRole
from app.schemas.history import BillingItemRow, BillingRow, MonthDetail, MonthSummary

logger = logging.getLogger("fontegest.history")

router = APIRouter(prefix="/history", tags=["history"])

_CURRENT_MONTH = datetime.now().strftime("%Y-%m")


def _is_current(month: str) -> bool:
    return month == datetime.now().strftime("%Y-%m")


async def _check_operator_access(
    db: AsyncSession, current_user: User, condominium_id: int
) -> None:
    """Raise 403 if operator is not assigned to this condominium."""
    if current_user.role == UserRole.operator:
        asgn = await db.execute(
            select(OperatorAssignment).where(
                OperatorAssignment.user_id == current_user.id,
                OperatorAssignment.condominium_id == condominium_id,
            )
        )
        if not asgn.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem acesso a este condomínio",
            )


# ── GET /{condominium_id} ─────────────────────────────────────────────


@router.get("/{condominium_id}", response_model=list[MonthSummary])
async def list_months(
    condominium_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """List all months with billing activity for a condominium."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    await _check_operator_access(db, current_user, condominium_id)

    # Get all billing records joined with their unit (to filter by condo)
    result = await db.execute(
        select(Billing, Unit)
        .join(Unit, Billing.unit_id == Unit.id)
        .where(Unit.condominium_id == condominium_id)
        .order_by(Billing.reference_month.desc())
    )
    rows = result.all()

    if not rows:
        return []

    # Group by reference_month
    months_data: dict[str, list[tuple[Billing, Unit]]] = {}
    for billing, unit in rows:
        months_data.setdefault(billing.reference_month, []).append((billing, unit))

    summaries: list[MonthSummary] = []

    for month, billing_units in sorted(months_data.items(), reverse=True):
        total_billed = 0.0
        total_received = 0.0
        qty_per_product: dict[str, int] = {}
        status_counts: dict[str, int] = {}

        billing_ids = [b.id for b, _ in billing_units]

        # Fetch all items for these billings in one query
        items_result = await db.execute(
            select(BillingItem, Product)
            .join(Product, BillingItem.product_id == Product.id)
            .where(BillingItem.billing_id.in_(billing_ids))
        )
        items_data = items_result.all()

        for bi, product in items_data:
            if bi.quantity > 0:
                qty_per_product[product.name] = (
                    qty_per_product.get(product.name, 0) + bi.quantity
                )

        for billing, _ in billing_units:
            total_billed += float(billing.total_amount)
            if billing.status == BillingStatus.paid:
                total_received += float(billing.total_amount)
            status_counts[billing.status.value] = (
                status_counts.get(billing.status.value, 0) + 1
            )

        summaries.append(
            MonthSummary(
                reference_month=month,
                total_billed=total_billed,
                total_received=total_received,
                total_units=len(billing_units),
                qty_per_product=qty_per_product,
                status_counts=status_counts,
                is_current=_is_current(month),
            )
        )

    return summaries


# ── GET /{condominium_id}/{reference_month} ───────────────────────────


@router.get("/{condominium_id}/{reference_month}", response_model=MonthDetail)
async def get_month_detail(
    condominium_id: int,
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Return full detail for a specific month: summary + per-unit billing rows."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    await _check_operator_access(db, current_user, condominium_id)

    result = await db.execute(
        select(Billing, Unit)
        .join(Unit, Billing.unit_id == Unit.id)
        .where(
            Unit.condominium_id == condominium_id,
            Billing.reference_month == reference_month,
        )
        .order_by(Unit.unit_code)
    )
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="Mês não encontrado")

    billing_ids = [b.id for b, _ in rows]

    # Load all billing items
    items_result = await db.execute(
        select(BillingItem, Product)
        .join(Product, BillingItem.product_id == Product.id)
        .where(BillingItem.billing_id.in_(billing_ids))
        .order_by(BillingItem.billing_id, Product.sort_order)
    )
    items_by_billing: dict[int, list[tuple[BillingItem, Product]]] = {}
    for bi, product in items_result.all():
        items_by_billing.setdefault(bi.billing_id, []).append((bi, product))

    # Load evidence counts
    evidence_result = await db.execute(
        select(Evidence.billing_id, func.count(Evidence.id).label("cnt"))
        .where(Evidence.billing_id.in_(billing_ids))
        .group_by(Evidence.billing_id)
    )
    evidence_counts: dict[int, int] = {row.billing_id: row.cnt for row in evidence_result}

    # Load residents
    unit_ids = [u.id for _, u in rows]
    residents_result = await db.execute(
        select(Resident).where(
            Resident.unit_id.in_(unit_ids),
            Resident.is_current.is_(True),
        )
    )
    residents_by_unit: dict[int, Resident] = {
        r.unit_id: r for r in residents_result.scalars().all()
    }

    # Build billing rows
    billing_rows: list[BillingRow] = []
    total_billed = 0.0
    total_received = 0.0
    qty_per_product: dict[str, int] = {}
    status_counts: dict[str, int] = {}

    for billing, unit in rows:
        resident = residents_by_unit.get(unit.id)
        ev_count = evidence_counts.get(billing.id, 0)

        items: list[BillingItemRow] = []
        for bi, product in items_by_billing.get(billing.id, []):
            if bi.quantity > 0:
                items.append(
                    BillingItemRow(
                        product_name=product.name,
                        quantity=bi.quantity,
                        unit_price=float(bi.unit_price_snapshot),
                    )
                )
                qty_per_product[product.name] = (
                    qty_per_product.get(product.name, 0) + bi.quantity
                )

        billing_rows.append(
            BillingRow(
                billing_id=billing.id,
                unit_code=unit.unit_code,
                resident_name=resident.name if resident else None,
                status=billing.status.value,
                total_amount=float(billing.total_amount),
                evidence_count=ev_count,
                items=items,
            )
        )

        total_billed += float(billing.total_amount)
        if billing.status == BillingStatus.paid:
            total_received += float(billing.total_amount)
        status_counts[billing.status.value] = (
            status_counts.get(billing.status.value, 0) + 1
        )

    summary = MonthSummary(
        reference_month=reference_month,
        total_billed=total_billed,
        total_received=total_received,
        total_units=len(rows),
        qty_per_product=qty_per_product,
        status_counts=status_counts,
        is_current=_is_current(reference_month),
    )

    return MonthDetail(summary=summary, billings=billing_rows)


# ── POST /{condominium_id}/{reference_month}/reopen ───────────────────


@router.post("/{condominium_id}/{reference_month}/reopen")
async def reopen_month(
    condominium_id: int,
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Revert all billings for a month back to draft status (admin only)."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    result = await db.execute(
        select(Billing, Unit)
        .join(Unit, Billing.unit_id == Unit.id)
        .where(
            Unit.condominium_id == condominium_id,
            Billing.reference_month == reference_month,
            Billing.status != BillingStatus.draft,
        )
    )
    rows = result.all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Nenhum lançamento encontrado para este mês ou todos já estão em rascunho",
        )

    reopened_count = 0
    for billing, _ in rows:
        billing.status = BillingStatus.draft
        reopened_count += 1

    await db.commit()

    logger.info(
        "Month reopened: admin_id=%s condo_id=%s month=%s reopened=%s timestamp=%s",
        current_user.id,
        condominium_id,
        reference_month,
        reopened_count,
        datetime.now().isoformat(),
    )

    return {"reopened_count": reopened_count}
