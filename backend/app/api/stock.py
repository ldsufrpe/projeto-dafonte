"""Stock control API endpoints.

Provides per-product stock overview (saldo_anterior, entradas, consumo_lancado,
saldo_atual, is_negative), entry CRUD, and a history chart endpoint.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_operator
from app.models.billing import Billing, BillingItem
from app.models.condominium import Condominium
from app.models.product import Product
from app.models.stock import StockAlertThreshold, StockEntry, StockEntryType
from app.models.unit import Unit
from app.models.user import User
from app.schemas.stock import (
    CreateStockEntryRequest,
    ProductStockOverview,
    StockChartResponse,
    StockEntryResponse,
    StockOverviewResponse,
    UpdateStockEntryRequest,
)

logger = logging.getLogger("fontegest.stock")

router = APIRouter(prefix="/stock", tags=["stock"])


# ── Helpers ───────────────────────────────────────────────────────────


def _prev_months(reference_month: str, n: int) -> list[str]:
    """Return a list of n months ending at reference_month (inclusive)."""
    year, month = map(int, reference_month.split("-"))
    result = []
    for i in range(n - 1, -1, -1):
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        result.append(f"{y:04d}-{m:02d}")
    return result


async def _compute_product_stats(
    db: AsyncSession,
    condominium_id: int,
    product_id: int,
    reference_month: str,
) -> tuple[int, int, int, int]:
    """Return (saldo_anterior, entradas, consumo_lancado, saldo_atual) for one product+month."""
    # Entradas this month
    q = await db.execute(
        select(func.coalesce(func.sum(StockEntry.quantity), 0)).where(
            StockEntry.condominium_id == condominium_id,
            StockEntry.product_id == product_id,
            StockEntry.reference_month == reference_month,
        )
    )
    entradas: int = q.scalar() or 0

    # Entradas before this month (cumulative)
    q = await db.execute(
        select(func.coalesce(func.sum(StockEntry.quantity), 0)).where(
            StockEntry.condominium_id == condominium_id,
            StockEntry.product_id == product_id,
            StockEntry.reference_month < reference_month,
        )
    )
    entradas_prev: int = q.scalar() or 0

    # Consumo this month (via billing items)
    q = await db.execute(
        select(func.coalesce(func.sum(BillingItem.quantity), 0))
        .join(Billing, BillingItem.billing_id == Billing.id)
        .join(Unit, Billing.unit_id == Unit.id)
        .where(
            Unit.condominium_id == condominium_id,
            BillingItem.product_id == product_id,
            Billing.reference_month == reference_month,
        )
    )
    consumo: int = q.scalar() or 0

    # Consumo before this month (cumulative)
    q = await db.execute(
        select(func.coalesce(func.sum(BillingItem.quantity), 0))
        .join(Billing, BillingItem.billing_id == Billing.id)
        .join(Unit, Billing.unit_id == Unit.id)
        .where(
            Unit.condominium_id == condominium_id,
            BillingItem.product_id == product_id,
            Billing.reference_month < reference_month,
        )
    )
    consumo_prev: int = q.scalar() or 0

    saldo_anterior = entradas_prev - consumo_prev
    saldo_atual = saldo_anterior + entradas - consumo
    return saldo_anterior, entradas, consumo, saldo_atual


# ── GET /{condominium_id}/chart ───────────────────────────────────────
# (must be defined BEFORE the parametric /{reference_month} route)


@router.get("/{condominium_id}/chart", response_model=StockChartResponse)
async def get_stock_chart(
    condominium_id: int,
    reference_month: str = Query(..., description="Last month to include (YYYY-MM)"),
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Return saldo_atual per product for the last N months (for line chart)."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    month_list = _prev_months(reference_month, months)

    products_result = await db.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sort_order)
    )
    products = products_result.scalars().all()

    series: dict[str, list[int]] = {}
    for product in products:
        values: list[int] = []
        for m in month_list:
            _, _, _, saldo_atual = await _compute_product_stats(db, condominium_id, product.id, m)
            values.append(saldo_atual)
        series[product.name] = values

    return StockChartResponse(months=month_list, series=series)


# ── GET /{condominium_id}/{reference_month} ───────────────────────────


@router.get("/{condominium_id}/{reference_month}", response_model=StockOverviewResponse)
async def get_stock_overview(
    condominium_id: int,
    reference_month: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Return stock overview per product and list of entries for the month."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    products_result = await db.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sort_order)
    )
    products = products_result.scalars().all()

    # Load alert thresholds for this condominium
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

    product_overviews: list[ProductStockOverview] = []
    for product in products:
        saldo_anterior, entradas, consumo, saldo_atual = await _compute_product_stats(
            db, condominium_id, product.id, reference_month
        )
        threshold = per_product_thresholds.get(product.id, global_threshold)
        is_below = saldo_atual < threshold if threshold is not None else saldo_atual < 0
        product_overviews.append(
            ProductStockOverview(
                product_id=product.id,
                product_name=product.name,
                capacity_liters=product.capacity_liters,
                saldo_anterior=saldo_anterior,
                entradas=entradas,
                consumo_lancado=consumo,
                saldo_atual=saldo_atual,
                is_negative=saldo_atual < 0,
                min_stock_alert=threshold,
                is_below_threshold=is_below,
            )
        )

    # Entries for this month
    entries_result = await db.execute(
        select(StockEntry, Product)
        .join(Product, StockEntry.product_id == Product.id)
        .where(
            StockEntry.condominium_id == condominium_id,
            StockEntry.reference_month == reference_month,
        )
        .order_by(StockEntry.created_at.desc())
    )
    entries_data = entries_result.all()

    entries: list[StockEntryResponse] = [
        StockEntryResponse(
            id=e.id,
            product_id=e.product_id,
            product_name=p.name,
            reference_month=e.reference_month,
            quantity=e.quantity,
            entry_type=e.entry_type.value,
            notes=e.notes,
            created_at=e.created_at,
        )
        for e, p in entries_data
    ]

    return StockOverviewResponse(
        condominium_id=condo.id,
        condominium_name=condo.name,
        reference_month=reference_month,
        products=product_overviews,
        entries=entries,
    )


# ── POST /entries ─────────────────────────────────────────────────────


@router.post("/entries", response_model=StockEntryResponse, status_code=201)
async def create_stock_entry(
    body: CreateStockEntryRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Register a new stock entry (abastecimento)."""
    condo = await db.get(Condominium, body.condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    product = await db.get(Product, body.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    try:
        entry_type = StockEntryType(body.entry_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo inválido: {body.entry_type}")

    entry = StockEntry(
        condominium_id=body.condominium_id,
        product_id=body.product_id,
        reference_month=body.reference_month,
        quantity=body.quantity,
        entry_type=entry_type,
        notes=body.notes,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return StockEntryResponse(
        id=entry.id,
        product_id=entry.product_id,
        product_name=product.name,
        reference_month=entry.reference_month,
        quantity=entry.quantity,
        entry_type=entry.entry_type.value,
        notes=entry.notes,
        created_at=entry.created_at,
    )


# ── PUT /entries/{entry_id} ───────────────────────────────────────────


@router.put("/entries/{entry_id}", response_model=StockEntryResponse)
async def update_stock_entry(
    entry_id: int,
    body: UpdateStockEntryRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Edit quantity or notes of an existing stock entry."""
    entry = await db.get(StockEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Lançamento de estoque não encontrado")

    product = await db.get(Product, entry.product_id)

    if body.quantity is not None:
        entry.quantity = body.quantity
    if body.notes is not None:
        entry.notes = body.notes

    await db.commit()
    await db.refresh(entry)

    return StockEntryResponse(
        id=entry.id,
        product_id=entry.product_id,
        product_name=product.name if product else "—",
        reference_month=entry.reference_month,
        quantity=entry.quantity,
        entry_type=entry.entry_type.value,
        notes=entry.notes,
        created_at=entry.created_at,
    )


# ── DELETE /entries/{entry_id} ────────────────────────────────────────


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_stock_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """Delete a stock entry."""
    entry = await db.get(StockEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Lançamento de estoque não encontrado")

    await db.delete(entry)
    await db.commit()
