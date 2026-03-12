"""Shared ERP sync logic.

Called by both the HTTP endpoints (erp.py) and the scheduled jobs (scheduler.py)
so that any fix in one place is reflected in both execution paths.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.condominium import Condominium
from app.models.product import PriceSource, Product, ProductPrice
from app.models.user import User, UserRole
from app.services.erp.base import ERPClientBase

logger = logging.getLogger("fontegest.erp.sync")


async def sync_users(session: AsyncSession, erp: ERPClientBase) -> dict:
    """Upsert users from ERP; deactivate users absent from ERP (except admin)."""
    users = await erp.get_users()
    erp_usernames = {u.username for u in users}
    created = updated = deactivated = 0

    for u in users:
        result = await session.execute(select(User).where(User.username == u.username))
        existing = result.scalar_one_or_none()
        role = UserRole.admin if u.is_admin else UserRole.operator

        if existing:
            if existing.hashed_password and not verify_password(u.password, existing.hashed_password):
                existing.hashed_password = hash_password(u.password)
            elif not existing.hashed_password:
                existing.hashed_password = hash_password(u.password)
            existing.full_name = u.full_name
            existing.email = u.email
            existing.role = role
            existing.is_active = True
            updated += 1
        else:
            session.add(
                User(
                    username=u.username,
                    full_name=u.full_name,
                    email=u.email,
                    hashed_password=hash_password(u.password),
                    role=role,
                    is_active=True,
                )
            )
            created += 1

    all_result = await session.execute(
        select(User).where(User.username != "admin", User.is_active.is_(True))
    )
    for user in all_result.scalars().all():
        if user.username not in erp_usernames:
            user.is_active = False
            deactivated += 1

    await session.commit()
    logger.info("sync-users: created=%d, updated=%d, deactivated=%d", created, updated, deactivated)
    return {"created": created, "updated": updated, "deactivated": deactivated}


async def sync_condominiums(session: AsyncSession, erp: ERPClientBase) -> dict:
    """Upsert condominiums and product prices from ERP."""
    condos = await erp.get_condominiums()
    today = date.today()

    prod_result = await session.execute(select(Product).where(Product.is_active.is_(True)))
    product_map = {p.erp_product_code: p for p in prod_result.scalars().all() if p.erp_product_code}

    created = updated = prices_synced = 0

    for c in condos:
        result = await session.execute(
            select(Condominium).where(Condominium.erp_code == c.erp_code)
        )
        condo = result.scalar_one_or_none()

        if condo:
            condo.name = c.name
            condo.address = c.address
            updated += 1
        else:
            condo = Condominium(
                name=c.name, address=c.address, erp_code=c.erp_code, onboarding_complete=False
            )
            session.add(condo)
            await session.flush()
            created += 1

        for code, price_str in c.prices.items():
            if not price_str or code not in product_map:
                continue
            product = product_map[code]
            price_val = Decimal(price_str)

            pp_result = await session.execute(
                select(ProductPrice).where(
                    ProductPrice.product_id == product.id,
                    ProductPrice.condominium_id == condo.id,
                    ProductPrice.valid_from == today,
                )
            )
            pp = pp_result.scalar_one_or_none()
            if pp:
                pp.unit_price = price_val
                pp.source = PriceSource.erp
            else:
                session.add(
                    ProductPrice(
                        product_id=product.id,
                        condominium_id=condo.id,
                        valid_from=today,
                        unit_price=price_val,
                        source=PriceSource.erp,
                    )
                )
            prices_synced += 1

    await session.commit()
    logger.info("sync-condominiums: created=%d, updated=%d, prices=%d", created, updated, prices_synced)
    return {"created": created, "updated": updated, "prices_synced": prices_synced}
