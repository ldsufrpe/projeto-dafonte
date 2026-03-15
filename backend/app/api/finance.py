from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.billing import Billing, BillingItem, BillingStatus
from app.models.condominium import CommissionRate, CommissionType, Condominium, OperatorAssignment
from app.models.product import Product
from app.models.unit import Unit
from app.models.user import User, UserRole
from app.schemas.finance import (
    CommissionConfigUpdate,
    CommissionRateCreate,
    CommissionRateOut,
    CommissionResult,
    OperatorPerformanceItem,
)

router = APIRouter(prefix="/finance", tags=["financeiro"])


# ── helpers ──────────────────────────────────────────────────────────


async def _calc_commission(
    db: AsyncSession,
    condo: Condominium,
    reference_month: str,
) -> tuple[Decimal, Decimal]:
    """Return (total_received, commission_due) for a condominium/month."""
    # total_received = SUM(Billing.total_amount) where status='paid'
    result = await db.execute(
        select(func.coalesce(func.sum(Billing.total_amount), 0))
        .join(Unit, Billing.unit_id == Unit.id)
        .where(
            Unit.condominium_id == condo.id,
            Billing.reference_month == reference_month,
            Billing.status == BillingStatus.paid,
        )
    )
    total_received = Decimal(str(result.scalar_one()))

    commission_due = Decimal("0")

    if condo.commission_type == CommissionType.fixed:
        commission_due = condo.commission_value or Decimal("0")

    elif condo.commission_type == CommissionType.percent:
        pct = condo.commission_value or Decimal("0")
        commission_due = total_received * pct / Decimal("100")

    elif condo.commission_type == CommissionType.per_unit:
        # SUM(BillingItem.quantity * CommissionRate.value_per_unit)
        # using the most recent CommissionRate where valid_from <= reference_month
        # We need to parse reference_month as a date for comparison
        ref_date = date.fromisoformat(reference_month + "-01")

        # Get all active products for this condominium that have commission rates
        rates_q = await db.execute(
            select(CommissionRate)
            .where(
                CommissionRate.condominium_id == condo.id,
                CommissionRate.valid_from <= ref_date,
            )
            .order_by(CommissionRate.product_id, CommissionRate.valid_from.desc())
        )
        all_rates = rates_q.scalars().all()

        # Deduplicate: keep only the most recent rate per product
        latest_rates: dict[int, Decimal] = {}
        for rate in all_rates:
            if rate.product_id not in latest_rates:
                latest_rates[rate.product_id] = rate.value_per_unit

        if latest_rates:
            # SUM(qty) per product for the month
            qty_q = await db.execute(
                select(BillingItem.product_id, func.sum(BillingItem.quantity))
                .join(Billing, BillingItem.billing_id == Billing.id)
                .join(Unit, Billing.unit_id == Unit.id)
                .where(
                    Unit.condominium_id == condo.id,
                    Billing.reference_month == reference_month,
                )
                .group_by(BillingItem.product_id)
            )
            for product_id, qty in qty_q.all():
                rate_val = latest_rates.get(product_id, Decimal("0"))
                commission_due += Decimal(str(qty)) * rate_val

    return total_received, commission_due


# ── endpoints ────────────────────────────────────────────────────────


@router.get("/commission/{condominium_id}/{reference_month}", response_model=CommissionResult)
async def get_commission(
    condominium_id: int,
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    # Operators can only see commission for their assigned condominiums
    if current_user.role == UserRole.operator:
        asgn = await db.execute(
            select(OperatorAssignment).where(
                OperatorAssignment.condominium_id == condominium_id,
                OperatorAssignment.user_id == current_user.id,
            )
        )
        if not asgn.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    total_received, commission_due = await _calc_commission(db, condo, reference_month)

    return CommissionResult(
        condominium_id=condo.id,
        condominium_name=condo.name,
        reference_month=reference_month,
        commission_type=condo.commission_type.value,
        commission_value=condo.commission_value,
        total_received=total_received,
        commission_due=commission_due,
    )


@router.get("/operator-performance/{reference_month}", response_model=list[OperatorPerformanceItem])
async def get_operator_performance(
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get condominiums accessible to this user
    if current_user.role == UserRole.admin:
        q = select(Condominium).order_by(Condominium.name)
    else:
        q = (
            select(Condominium)
            .join(OperatorAssignment, Condominium.id == OperatorAssignment.condominium_id)
            .where(OperatorAssignment.user_id == current_user.id)
            .order_by(Condominium.name)
        )

    result = await db.execute(q)
    condominiums = result.scalars().all()

    items: list[OperatorPerformanceItem] = []
    for condo in condominiums:
        # total_billed = SUM where status != draft
        billed_q = await db.execute(
            select(func.coalesce(func.sum(Billing.total_amount), 0))
            .join(Unit, Billing.unit_id == Unit.id)
            .where(
                Unit.condominium_id == condo.id,
                Billing.reference_month == reference_month,
                Billing.status != BillingStatus.draft,
            )
        )
        total_billed = Decimal(str(billed_q.scalar_one()))

        total_received, commission_due = await _calc_commission(db, condo, reference_month)

        success_rate = Decimal("0")
        if total_billed > 0:
            success_rate = (total_received / total_billed * 100).quantize(Decimal("0.1"))

        items.append(
            OperatorPerformanceItem(
                condominium_id=condo.id,
                condominium_name=condo.name,
                total_billed=total_billed,
                total_received=total_received,
                success_rate=success_rate,
                commission_due=commission_due,
            )
        )

    return items


# ── commission config (on condominium router) ────────────────────────


@router.get("/condominiums/{condominium_id}/commission-config", response_model=dict)
async def get_commission_config(
    condominium_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")
    return {
        "commission_type": condo.commission_type.value if condo.commission_type else "fixed",
        "commission_value": float(condo.commission_value) if condo.commission_value is not None else None,
    }


@router.put("/condominiums/{condominium_id}/commission-config", response_model=dict)
async def update_commission_config(
    condominium_id: int,
    body: CommissionConfigUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    try:
        condo.commission_type = CommissionType(body.commission_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Tipo inválido: {body.commission_type}")

    condo.commission_value = body.commission_value
    await db.commit()
    return {"ok": True, "commission_type": condo.commission_type.value, "commission_value": str(condo.commission_value)}


@router.post("/condominiums/{condominium_id}/commission-rates", response_model=CommissionRateOut, status_code=status.HTTP_201_CREATED)
async def create_commission_rate(
    condominium_id: int,
    body: CommissionRateCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    product = await db.get(Product, body.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    rate = CommissionRate(
        condominium_id=condominium_id,
        product_id=body.product_id,
        value_per_unit=body.value_per_unit,
        valid_from=body.valid_from,
    )
    db.add(rate)
    await db.commit()
    await db.refresh(rate)

    return CommissionRateOut(
        id=rate.id,
        condominium_id=rate.condominium_id,
        product_id=rate.product_id,
        product_name=product.name,
        value_per_unit=rate.value_per_unit,
        valid_from=rate.valid_from,
    )


@router.get("/condominiums/{condominium_id}/commission-rates", response_model=list[CommissionRateOut])
async def list_commission_rates(
    condominium_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CommissionRate, Product.name)
        .join(Product, CommissionRate.product_id == Product.id)
        .where(CommissionRate.condominium_id == condominium_id)
        .order_by(Product.sort_order, CommissionRate.valid_from.desc())
    )

    items: list[CommissionRateOut] = []
    for rate, product_name in result.all():
        items.append(
            CommissionRateOut(
                id=rate.id,
                condominium_id=rate.condominium_id,
                product_id=rate.product_id,
                product_name=product_name,
                value_per_unit=rate.value_per_unit,
                valid_from=rate.valid_from,
            )
        )
    return items
