"""APScheduler-based ERP sync scheduler.

Runs sync_users and sync_condominiums jobs on a CRON schedule.
Uses sync_service.py so the logic stays in one place — shared with HTTP endpoints.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.erp.factory import get_erp_client
from app.services.erp.sync_service import sync_condominiums, sync_users

logger = logging.getLogger("fontegest.scheduler")

scheduler = AsyncIOScheduler()


async def sync_users_job() -> None:
    """Scheduled job: sync users from ERP."""
    erp = get_erp_client()
    async with AsyncSessionLocal() as session:
        result = await sync_users(session, erp)
        logger.info("⏰ sync-users job: %s", result)


async def sync_condominiums_job() -> None:
    """Scheduled job: sync condominiums and prices from ERP."""
    erp = get_erp_client()
    async with AsyncSessionLocal() as session:
        result = await sync_condominiums(session, erp)
        logger.info("⏰ sync-condominiums job: %s", result)


def start_scheduler() -> None:
    """Start the APScheduler with configured CRON schedule."""
    cron = settings.SYNC_CRON
    logger.info("📅 Starting scheduler with SYNC_CRON='%s'", cron)

    parts = cron.split()
    if len(parts) != 5:
        logger.error("Invalid SYNC_CRON format: '%s'. Expected 5 fields.", cron)
        return

    trigger = CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )

    scheduler.add_job(sync_users_job, trigger, id="sync_users", replace_existing=True)
    scheduler.add_job(sync_condominiums_job, trigger, id="sync_condominiums", replace_existing=True)
    scheduler.start()
    logger.info("✅ Scheduler started with 2 jobs")


def stop_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler stopped")
