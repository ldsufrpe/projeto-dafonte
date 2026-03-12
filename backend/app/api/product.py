from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.product import Product, ProductPrice, PriceSource
from app.models.user import User
from app.schemas.product import (
    ProductOut,
    ProductPriceCreate,
    ProductPriceOut,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["produtos"])


# ── helpers ──────────────────────────────────────────────────────────


async def _get_current_price(
    db: AsyncSession, product_id: int, condominium_id: Optional[int]
) -> Optional[ProductPrice]:
    """Return the most recent price for a product/condominium pair."""
    if condominium_id is not None:
        result = await db.execute(
            select(ProductPrice)
            .where(
                ProductPrice.product_id == product_id,
                ProductPrice.condominium_id == condominium_id,
                ProductPrice.valid_from <= date.today(),
            )
            .order_by(ProductPrice.valid_from.desc())
            .limit(1)
        )
        price = result.scalar_one_or_none()
        if price:
            return price

    # Fallback to global price (condominium_id IS NULL)
    result = await db.execute(
        select(ProductPrice)
        .where(
            ProductPrice.product_id == product_id,
            ProductPrice.condominium_id.is_(None),
            ProductPrice.valid_from <= date.today(),
        )
        .order_by(ProductPrice.valid_from.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── endpoints ────────────────────────────────────────────────────────


@router.get("", response_model=list[ProductOut])
async def list_products(
    condominium_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all products (active and inactive) with current price for the given condominium."""
    result = await db.execute(
        select(Product).order_by(Product.sort_order, Product.name)
    )
    products = result.scalars().all()

    items: list[ProductOut] = []
    for p in products:
        price_record = await _get_current_price(db, p.id, condominium_id)
        items.append(
            ProductOut(
                id=p.id,
                name=p.name,
                capacity_liters=p.capacity_liters,
                erp_product_code=p.erp_product_code,
                is_active=p.is_active,
                sort_order=p.sort_order,
                current_price=price_record.unit_price if price_record else None,
            )
        )
    return items


@router.patch("/{product_id}/active", response_model=ProductOut)
async def toggle_product_active(
    product_id: int,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Toggle is_active on a product. Products are managed by the ERP — only visibility can be changed here."""
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    if body.is_active is not None:
        product.is_active = body.is_active

    await db.commit()
    await db.refresh(product)

    price_record = await _get_current_price(db, product.id, None)
    return ProductOut(
        id=product.id,
        name=product.name,
        capacity_liters=product.capacity_liters,
        erp_product_code=product.erp_product_code,
        is_active=product.is_active,
        sort_order=product.sort_order,
        current_price=price_record.unit_price if price_record else None,
    )


@router.post("/{product_id}/prices", response_model=ProductPriceOut, status_code=status.HTTP_201_CREATED)
async def create_price(
    product_id: int,
    body: ProductPriceCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    price = ProductPrice(
        product_id=product_id,
        condominium_id=body.condominium_id,
        valid_from=body.valid_from,
        unit_price=body.unit_price,
        source=PriceSource.local,
    )
    db.add(price)
    await db.commit()
    await db.refresh(price)
    return price


@router.get("/{product_id}/prices", response_model=list[ProductPriceOut])
async def list_prices(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProductPrice)
        .where(ProductPrice.product_id == product_id)
        .order_by(ProductPrice.valid_from.desc())
    )
    return result.scalars().all()
