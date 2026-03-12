"""ERP synchronization and submission endpoints.

All endpoints use the factory pattern to get the ERP client,
so they work transparently with both MockERPClient and future DataSnapClient.
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_admin, require_operator
from app.models.billing import Billing, BillingStatus
from app.models.condominium import Condominium
from app.models.product import Product
from app.models.unit import Resident, Unit
from app.models.user import User
from app.services.erp.base import ERPClientBase
from app.services.erp.factory import get_erp_client
from app.services.erp.sync_service import sync_condominiums, sync_users

logger = logging.getLogger("fontegest.erp")

router = APIRouter(prefix="/erp", tags=["erp"])


# ── GET /mode ───────────────────────────────────────────────────────


@router.get("/mode")
async def erp_mode():
    """Return current ERP mode for frontend indicator."""
    return {
        "erp_mode": settings.ERP_MODE,
        "is_mock": settings.ERP_MODE == "mock",
    }


# ── POST /sync-users ────────────────────────────────────────────────


@router.post("/sync-users")
async def sync_users_endpoint(
    db: AsyncSession = Depends(get_db),
    erp: ERPClientBase = Depends(get_erp_client),
    _: User = Depends(require_admin),
):
    """Sync users from ERP. Upsert by username. Admin only."""
    return await sync_users(db, erp)


# ── POST /sync-condominiums ──────────────────────────────────────────


@router.post("/sync-condominiums")
async def sync_condominiums_endpoint(
    db: AsyncSession = Depends(get_db),
    erp: ERPClientBase = Depends(get_erp_client),
    _: User = Depends(require_admin),
):
    """Sync condominiums and product prices from ERP. Admin only."""
    return await sync_condominiums(db, erp)


# ── POST /sync-residents/{condominium_id} ────────────────────────────


@router.post("/sync-residents/{condominium_id}")
async def sync_residents(
    condominium_id: int,
    db: AsyncSession = Depends(get_db),
    erp: ERPClientBase = Depends(get_erp_client),
    _: User = Depends(require_admin),
):
    """Sync units and residents for a condominium. Admin only."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Condomínio não encontrado")

    residents = await erp.get_residents(condo.erp_code)
    created = 0
    updated = 0

    for r in residents:
        # Upsert Unit
        unit_result = await db.execute(
            select(Unit).where(Unit.condominium_id == condo.id, Unit.unit_code == r.unit_code)
        )
        unit = unit_result.scalar_one_or_none()
        if not unit:
            unit = Unit(condominium_id=condo.id, unit_code=r.unit_code, is_active=True)
            db.add(unit)
            await db.flush()

        # Upsert Resident
        res_result = await db.execute(
            select(Resident).where(Resident.unit_id == unit.id, Resident.is_current.is_(True))
        )
        resident = res_result.scalar_one_or_none()
        if resident:
            resident.name = r.resident_name
            resident.cpf_masked = r.cpf_masked
            updated += 1
        else:
            db.add(
                Resident(
                    unit_id=unit.id,
                    name=r.resident_name,
                    cpf_masked=r.cpf_masked,
                    is_current=r.is_current,
                )
            )
            created += 1

    await db.commit()
    logger.info("sync-residents(%s): created=%d, updated=%d", condo.name, created, updated)
    return {"condominium": condo.name, "created": created, "updated": updated}


# ── POST /sync-payments/{condominium_id}/{reference_month} ───────────


@router.post("/sync-payments/{condominium_id}/{reference_month}")
async def sync_payments(
    condominium_id: int,
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    erp: ERPClientBase = Depends(get_erp_client),
    _: User = Depends(require_admin),
):
    """Sync payment statuses from ERP for a given month. Admin only."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Condomínio não encontrado")

    statuses = await erp.get_payment_status(condo.erp_code, reference_month)
    updated_count = 0

    for s in statuses:
        # Find unit
        unit_result = await db.execute(
            select(Unit).where(Unit.condominium_id == condo.id, Unit.unit_code == s.unit_code)
        )
        unit = unit_result.scalar_one_or_none()
        if not unit:
            continue

        # Find billing
        billing_result = await db.execute(
            select(Billing).where(
                Billing.unit_id == unit.id, Billing.reference_month == reference_month
            )
        )
        billing = billing_result.scalar_one_or_none()
        if not billing:
            continue

        # Map status
        status_map = {
            "paid": BillingStatus.paid,
            "open": BillingStatus.open,
            "no_consumption": BillingStatus.no_consumption,
        }
        new_status = status_map.get(s.status)
        if new_status:
            billing.status = new_status
            billing.erp_invoice_id = s.erp_invoice_id
            billing.days_overdue = s.days_overdue
            updated_count += 1

    await db.commit()
    logger.info("sync-payments(%s, %s): %d updated", condo.name, reference_month, updated_count)
    return {"condominium": condo.name, "reference_month": reference_month, "updated": updated_count}


# ── POST /submit-billing/{condominium_id}/{reference_month} ──────────


@router.post("/submit-billing/{condominium_id}/{reference_month}")
async def submit_billing(
    condominium_id: int,
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    erp: ERPClientBase = Depends(get_erp_client),
    _: User = Depends(require_operator),
):
    """Submit billing to ERP and persist invoice IDs. Operator + Admin."""
    from app.models.billing import BillingItem
    from app.services.erp.schemas import BillingItemPayload, BillingPayloadSchema

    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Condomínio não encontrado")

    # Fetch all billings for this month
    billing_result = await db.execute(
        select(Billing, Unit)
        .join(Unit, Billing.unit_id == Unit.id)
        .where(
            Unit.condominium_id == condo.id,
            Billing.reference_month == reference_month,
        )
    )
    rows = billing_result.all()

    # Build payload items
    items: list[BillingItemPayload] = []
    billing_by_unit: dict[str, Billing] = {}

    for billing, unit in rows:
        billing_by_unit[unit.unit_code] = billing

        # Get billing items
        bi_result = await db.execute(
            select(BillingItem, Product)
            .join(Product, BillingItem.product_id == Product.id)
            .where(BillingItem.billing_id == billing.id)
        )
        for bi, product in bi_result.all():
            items.append(
                BillingItemPayload(
                    unit_code=unit.unit_code,
                    erp_product_code=product.erp_product_code or "",
                    quantity=bi.quantity,
                    unit_price=str(bi.unit_price_snapshot),
                )
            )

    payload = BillingPayloadSchema(
        erp_code=condo.erp_code,
        reference_month=reference_month,
        items=items,
    )

    result = await erp.submit_billing(payload)

    # Persist invoice IDs
    for r in result.results:
        if r.success and r.unit_code in billing_by_unit:
            billing = billing_by_unit[r.unit_code]
            billing.erp_invoice_id = r.erp_invoice_id
            billing.status = BillingStatus.submitted

    await db.commit()
    logger.info(
        "submit-billing(%s, %s): submitted=%d, skipped=%d",
        condo.name,
        reference_month,
        result.submitted_count,
        result.skipped_count,
    )
    return result.model_dump()
