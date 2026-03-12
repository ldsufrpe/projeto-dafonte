"""Database seed for development environment.

Populates the database with mock data from the ERP mock client on startup.
Only runs when ENV=development and the database is empty/needs seeding.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.billing import Billing, BillingItem, BillingStatus
from app.models.condominium import Condominium
from app.models.product import PriceSource, Product, ProductPrice
from app.models.unit import Resident, Unit
from app.models.user import User, UserRole
from app.services.erp.mock_client import MockERPClient

logger = logging.getLogger("fontegest.seed")

# Fixed product catalog (columns from VW_PESSOA_PRECOS)
PRODUCT_CATALOG = [
    {"erp_product_code": "INDAIA20LT", "name": "Galão 20L INDAIÁ", "capacity_liters": 20, "sort_order": 1},
    {"erp_product_code": "INDAIA10L", "name": "Galão 10L INDAIÁ", "capacity_liters": 10, "sort_order": 2},
    {"erp_product_code": "IAIA20L", "name": "Galão 20L IAIÁ", "capacity_liters": 20, "sort_order": 3},
]


async def run_seed(session: AsyncSession) -> None:
    """Run full seed sequence. Idempotent — safe to call multiple times."""
    if settings.ENV != "development":
        logger.info("Seed skipped: ENV=%s (only runs in development)", settings.ENV)
        return

    erp = MockERPClient()
    logger.info("🌱 Starting database seed (ERP_MODE=mock)...")

    await _seed_products(session)
    await _seed_admin(session)
    await _seed_users(session, erp)
    product_map = await _get_product_map(session)
    await _seed_condominiums(session, erp, product_map)
    await _seed_residents_and_billing(session, erp, product_map)

    await session.commit()
    logger.info("✅ Seed completed successfully")


async def _seed_products(session: AsyncSession) -> None:
    """Upsert the 3 fixed products by erp_product_code."""
    for p in PRODUCT_CATALOG:
        result = await session.execute(
            select(Product).where(Product.erp_product_code == p["erp_product_code"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.name = p["name"]
            existing.capacity_liters = p["capacity_liters"]
            existing.sort_order = p["sort_order"]
            existing.is_active = True
        else:
            session.add(Product(**p))
    await session.flush()
    logger.info("  📦 Products seeded (3 items)")


async def _seed_admin(session: AsyncSession) -> None:
    """Create local admin user if it doesn't exist."""
    result = await session.execute(select(User).where(User.username == "admin"))
    if result.scalar_one_or_none():
        return
    session.add(
        User(
            username="admin",
            full_name="Administrador Local",
            hashed_password=hash_password("admin123"),
            role=UserRole.admin,
            is_active=True,
        )
    )
    await session.flush()
    logger.info("  👤 Admin user created (admin/admin123)")


async def _seed_users(session: AsyncSession, erp: MockERPClient) -> None:
    """Sync users from mock ERP."""
    users = await erp.get_users()
    created = 0
    updated = 0

    for u in users:
        result = await session.execute(select(User).where(User.username == u.username))
        existing = result.scalar_one_or_none()

        role = UserRole.admin if u.is_admin else UserRole.operator

        if existing:
            # Update password if changed
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

    await session.flush()
    logger.info("  👥 Users synced (created=%d, updated=%d)", created, updated)


async def _get_product_map(session: AsyncSession) -> dict[str, Product]:
    """Return dict mapping erp_product_code → Product."""
    result = await session.execute(select(Product).where(Product.is_active.is_(True)))
    return {p.erp_product_code: p for p in result.scalars().all() if p.erp_product_code}


async def _seed_condominiums(
    session: AsyncSession, erp: MockERPClient, product_map: dict[str, Product]
) -> None:
    """Sync condominiums and their product prices from mock ERP."""
    condos = await erp.get_condominiums()
    today = date.today()

    for c in condos:
        result = await session.execute(
            select(Condominium).where(Condominium.erp_code == c.erp_code)
        )
        condo = result.scalar_one_or_none()

        if condo:
            condo.name = c.name
            condo.address = c.address
        else:
            condo = Condominium(
                name=c.name,
                address=c.address,
                erp_code=c.erp_code,
                onboarding_complete=False,
            )
            session.add(condo)
            await session.flush()  # get condo.id

        # Upsert ProductPrice for each non-null price
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

    await session.flush()
    logger.info("  🏢 Condominiums synced (%d items)", len(condos))


async def _seed_residents_and_billing(
    session: AsyncSession, erp: MockERPClient, product_map: dict[str, Product]
) -> None:
    """Seed residents and billing data for each condominium."""
    result = await session.execute(select(Condominium))
    condos = result.scalars().all()

    for condo in condos:
        residents = await erp.get_residents(condo.erp_code)
        if not residents:
            continue

        # Get product prices for this condominium
        pp_result = await session.execute(
            select(ProductPrice).where(ProductPrice.condominium_id == condo.id)
        )
        prices = {pp.product_id: pp for pp in pp_result.scalars().all()}

        for r in residents:
            # Upsert Unit
            unit_result = await session.execute(
                select(Unit).where(
                    Unit.condominium_id == condo.id,
                    Unit.unit_code == r.unit_code,
                )
            )
            unit = unit_result.scalar_one_or_none()
            if not unit:
                unit = Unit(condominium_id=condo.id, unit_code=r.unit_code, is_active=True)
                session.add(unit)
                await session.flush()

            # Upsert Resident
            res_result = await session.execute(
                select(Resident).where(
                    Resident.unit_id == unit.id, Resident.is_current.is_(True)
                )
            )
            resident = res_result.scalar_one_or_none()
            if resident:
                resident.name = r.resident_name
                resident.cpf_masked = r.cpf_masked
            else:
                resident = Resident(
                    unit_id=unit.id,
                    name=r.resident_name,
                    cpf_masked=r.cpf_masked,
                    is_current=r.is_current,
                )
                session.add(resident)
                await session.flush()

            # Create Billing for Dec/2025 if not exists
            ref_month = "2025-12"
            billing_result = await session.execute(
                select(Billing).where(
                    Billing.unit_id == unit.id,
                    Billing.reference_month == ref_month,
                )
            )
            billing = billing_result.scalar_one_or_none()
            if not billing:
                billing = Billing(
                    unit_id=unit.id,
                    resident_id=resident.id,
                    reference_month=ref_month,
                    status=BillingStatus.draft,
                    total_amount=Decimal("0"),
                )
                session.add(billing)
                await session.flush()

                # Create BillingItem for each product with price
                for product_id, pp in prices.items():
                    session.add(
                        BillingItem(
                            billing_id=billing.id,
                            product_id=product_id,
                            product_price_id=pp.id,
                            quantity=0,
                            unit_price_snapshot=pp.unit_price,
                            line_total=Decimal("0"),
                        )
                    )

        logger.info(
            "  🏠 %s: %d units + residents + billing seeded",
            condo.name,
            len(residents),
        )

    await session.flush()
