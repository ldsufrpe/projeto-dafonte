"""Billing API endpoints.

Handles the billing grid (lançamento), quantity updates,
resident edits with lazy activation, and mesh generation.
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_operator
from app.models.billing import Billing, BillingItem, BillingStatus
from app.models.condominium import Condominium
from app.models.product import Product, ProductPrice
from app.models.unit import Resident, Unit
from app.models.user import User, UserRole
from app.schemas.billing import (
    BillingGridResponse,
    BillingItemResponse,
    BillingRowResponse,
    BillingSummary,
    GenerateMeshRequest,
    ProductHeader,
    ResidentInfo,
    UpdateQuantityRequest,
    UpdateResidentRequest,
)

logger = logging.getLogger("fontegest.billing")

router = APIRouter(prefix="/billing", tags=["billing"])


# ── GET /{condominium_id}/{reference_month} ──────────────────────────


@router.get("/{condominium_id}/{reference_month}", response_model=BillingGridResponse)
async def get_billing_grid(
    condominium_id: int,
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    await _check_operator_access(db, current_user, condominium_id)
    """Return billing grid. Auto-creates Billing+BillingItems for new months."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    # Get active products with prices for this condominium
    products_with_prices = await _get_products_with_prices(db, condominium_id)
    if not products_with_prices:
        return BillingGridResponse(
            condominium_id=condo.id,
            condominium_name=condo.name,
            reference_month=reference_month,
            products=[],
            rows=[],
            summary=BillingSummary(),
        )

    # Get all units for this condominium
    units_result = await db.execute(
        select(Unit)
        .where(Unit.condominium_id == condominium_id, Unit.is_active.is_(True))
        .order_by(Unit.unit_code)
    )
    units = units_result.scalars().all()

    # Ensure Billing + BillingItems exist for each unit
    for unit in units:
        await _ensure_billing(db, unit, reference_month, products_with_prices)
    await db.commit()  # Persist newly created billings so they're visible to other requests

    # Build response rows
    rows: list[BillingRowResponse] = []
    summary = BillingSummary(total_units=len(units), totals_by_product={})

    for unit in units:
        billing_result = await db.execute(
            select(Billing).where(
                Billing.unit_id == unit.id,
                Billing.reference_month == reference_month,
            )
        )
        billing = billing_result.scalar_one_or_none()
        if not billing:
            continue

        # Get resident
        res_result = await db.execute(
            select(Resident).where(
                Resident.unit_id == unit.id, Resident.is_current.is_(True)
            )
        )
        resident = res_result.scalar_one_or_none()

        # Get billing items
        bi_result = await db.execute(
            select(BillingItem, Product)
            .join(Product, BillingItem.product_id == Product.id)
            .where(BillingItem.billing_id == billing.id)
            .order_by(Product.sort_order)
        )
        items_data = bi_result.all()

        items: list[BillingItemResponse] = []
        has_consumption = False
        for bi, product in items_data:
            items.append(
                BillingItemResponse(
                    id=bi.id,
                    product_id=product.id,
                    erp_product_code=product.erp_product_code or "",
                    product_name=product.name,
                    quantity=bi.quantity,
                    unit_price=bi.unit_price_snapshot,
                    line_total=bi.line_total,
                )
            )
            if bi.quantity > 0:
                has_consumption = True

            # Accumulate product totals
            summary.totals_by_product[product.id] = (
                summary.totals_by_product.get(product.id, 0) + bi.quantity
            )

        row = BillingRowResponse(
            billing_id=billing.id,
            unit_id=unit.id,
            unit_code=unit.unit_code,
            resident=ResidentInfo(
                id=resident.id if resident else None,
                name=resident.name if resident else None,
                cpf_masked=resident.cpf_masked if resident else None,
                phone=resident.phone if resident else None,
            ),
            items=items,
            total_amount=billing.total_amount,
            status=billing.status.value,
            days_overdue=billing.days_overdue,
            erp_invoice_id=billing.erp_invoice_id,
            resident_changed=billing.resident_changed,
            has_consumption=has_consumption,
        )
        rows.append(row)

        # Summary accumulation
        if billing.status == BillingStatus.paid:
            summary.total_arrecadado += billing.total_amount
        elif billing.status in (BillingStatus.open, BillingStatus.submitted):
            summary.total_em_aberto += billing.total_amount
        summary.total_faturado += billing.total_amount

    # Build product headers
    product_headers = [
        ProductHeader(
            id=p.id,
            erp_product_code=p.erp_product_code or "",
            name=p.name,
            capacity_liters=p.capacity_liters,
            sort_order=p.sort_order,
            unit_price=price,
        )
        for p, price in products_with_prices
    ]

    return BillingGridResponse(
        condominium_id=condo.id,
        condominium_name=condo.name,
        reference_month=reference_month,
        products=product_headers,
        rows=rows,
        summary=summary,
    )


# ── PATCH /item/{billing_item_id} ────────────────────────────────────


@router.patch("/item/{billing_item_id}")
async def update_billing_item(
    billing_item_id: int,
    body: UpdateQuantityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Update quantity of a billing item, recalculate totals."""
    bi = await db.get(BillingItem, billing_item_id)
    if not bi:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    billing = await db.get(Billing, bi.billing_id)
    if not billing:
        raise HTTPException(status_code=404, detail="Billing não encontrado")
        
    await _check_operator_access(db, current_user, billing.unit.condominium_id if hasattr(billing, "unit") else (await db.get(Unit, billing.unit_id)).condominium_id)

    # Prevent edits on submitted/paid billings
    if billing.status in (BillingStatus.submitted, BillingStatus.paid):
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível editar lançamento com status '{billing.status.value}'"
        )

    # Update item
    bi.quantity = body.quantity
    bi.line_total = Decimal(str(body.quantity)) * bi.unit_price_snapshot

    # Recalculate billing total
    all_items_result = await db.execute(
        select(BillingItem).where(BillingItem.billing_id == billing.id)
    )
    all_items = all_items_result.scalars().all()
    billing.total_amount = sum(item.line_total for item in all_items)

    # Advance/revert status based on whether any item has consumption
    has_consumption = any(item.quantity > 0 for item in all_items)
    if has_consumption:
        if billing.status in (BillingStatus.draft, BillingStatus.no_consumption):
            billing.status = BillingStatus.pending_submission
    else:
        if billing.status == BillingStatus.pending_submission:
            billing.status = BillingStatus.draft

    await db.commit()

    return {
        "item_id": bi.id,
        "quantity": bi.quantity,
        "line_total": str(bi.line_total),
        "billing_total": str(billing.total_amount),
        "billing_status": billing.status.value,
    }


# ── PATCH /{billing_id}/resident ─────────────────────────────────────


@router.patch("/{billing_id}/resident")
async def update_billing_resident(
    billing_id: int,
    body: UpdateResidentRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Update resident info. Blocked if no consumption (lazy activation)."""
    billing = await db.get(Billing, billing_id)
    if not billing:
        raise HTTPException(status_code=404, detail="Billing não encontrado")

    unit = await db.get(Unit, billing.unit_id)
    await _check_operator_access(db, current_user, unit.condominium_id)

    # Lazy activation check
    items_result = await db.execute(
        select(BillingItem).where(BillingItem.billing_id == billing.id)
    )
    items = items_result.scalars().all()
    total_qty = sum(i.quantity for i in items)
    if total_qty == 0:
        raise HTTPException(
            status_code=400,
            detail="Preencha ao menos uma quantidade antes de editar dados do morador",
        )

    # Find or create resident
    unit = await db.get(Unit, billing.unit_id)
    res_result = await db.execute(
        select(Resident).where(
            Resident.unit_id == unit.id, Resident.is_current.is_(True)
        )
    )
    resident = res_result.scalar_one_or_none()

    if resident:
        if body.name is not None:
            resident.name = body.name
        if body.cpf_masked is not None:
            resident.cpf_masked = body.cpf_masked
        if body.phone is not None:
            resident.phone = body.phone
    else:
        resident = Resident(
            unit_id=unit.id,
            name=body.name,
            cpf_masked=body.cpf_masked,
            phone=body.phone,
            is_current=True,
        )
        db.add(resident)
        await db.flush()

    billing.resident_id = resident.id
    billing.resident_changed = True
    await db.commit()

    return {
        "billing_id": billing.id,
        "resident_id": resident.id,
        "name": resident.name,
        "cpf_masked": resident.cpf_masked,
        "phone": resident.phone,
    }


# ── POST /generate-mesh ─────────────────────────────────────────────


@router.post("/generate-mesh")
async def generate_mesh(
    body: GenerateMeshRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    await _check_operator_access(db, current_user, body.condominium_id)
    """Generate units in range with blank billing for a given month."""
    condo = await db.get(Condominium, body.condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    products_with_prices = await _get_products_with_prices(db, body.condominium_id)
    created_units = 0

    for code_int in range(body.unit_start, body.unit_end + 1):
        unit_code = str(code_int)

        # Check if unit exists
        existing = await db.execute(
            select(Unit).where(
                Unit.condominium_id == condo.id, Unit.unit_code == unit_code
            )
        )
        unit = existing.scalar_one_or_none()
        if not unit:
            unit = Unit(condominium_id=condo.id, unit_code=unit_code, is_active=True)
            db.add(unit)
            await db.flush()
            created_units += 1

        await _ensure_billing(db, unit, body.reference_month, products_with_prices)

    await db.commit()
    return {
        "condominium": condo.name,
        "created_units": created_units,
        "range": f"{body.unit_start}-{body.unit_end}",
        "reference_month": body.reference_month,
    }


# ── Helpers ──────────────────────────────────────────────────────────

async def _check_operator_access(db: AsyncSession, user: User, condominium_id: int) -> None:
    if user.role == UserRole.admin:
        return
    from app.models.condominium import OperatorAssignment
    asgn = await db.execute(
        select(OperatorAssignment).where(
            OperatorAssignment.condominium_id == condominium_id,
            OperatorAssignment.user_id == user.id,
        )
    )
    if not asgn.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado ao condomínio")


async def _get_products_with_prices(
    db: AsyncSession, condominium_id: int
) -> list[tuple[Product, Decimal]]:
    """Get active products with their latest price for a condominium."""
    result = await db.execute(
        select(Product, ProductPrice.unit_price)
        .join(ProductPrice, Product.id == ProductPrice.product_id)
        .where(
            Product.is_active.is_(True),
            ProductPrice.condominium_id == condominium_id,
        )
        .order_by(Product.sort_order, ProductPrice.valid_from.desc())
    )
    # Deduplicate to get latest price per product
    seen: set[int] = set()
    products: list[tuple[Product, Decimal]] = []
    for product, price in result.all():
        if product.id not in seen:
            seen.add(product.id)
            products.append((product, price))
    return products


async def _ensure_billing(
    db: AsyncSession,
    unit: Unit,
    reference_month: str,
    products_with_prices: list[tuple[Product, Decimal]],
) -> Billing:
    """Ensure Billing + BillingItems exist for a unit+month. Creates if missing."""
    billing_result = await db.execute(
        select(Billing).where(
            Billing.unit_id == unit.id,
            Billing.reference_month == reference_month,
        )
    )
    billing = billing_result.scalar_one_or_none()

    if billing:
        return billing

    # Get current resident
    res_result = await db.execute(
        select(Resident).where(
            Resident.unit_id == unit.id, Resident.is_current.is_(True)
        )
    )
    resident = res_result.scalar_one_or_none()

    billing = Billing(
        unit_id=unit.id,
        resident_id=resident.id if resident else None,
        reference_month=reference_month,
        status=BillingStatus.draft,
        total_amount=Decimal("0"),
    )
    db.add(billing)
    await db.flush()

    # Create BillingItem for each product
    for product, price in products_with_prices:
        # Check if price record exists
        pp_result = await db.execute(
            select(ProductPrice).where(
                ProductPrice.product_id == product.id,
                ProductPrice.condominium_id == unit.condominium_id,
            ).order_by(ProductPrice.valid_from.desc())
        )
        pp = pp_result.scalars().first()

        db.add(
            BillingItem(
                billing_id=billing.id,
                product_id=product.id,
                product_price_id=pp.id if pp else None,
                quantity=0,
                unit_price_snapshot=price,
                line_total=Decimal("0"),
            )
        )

    await db.flush()
    return billing
