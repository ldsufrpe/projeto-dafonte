"""Mock ERP client for local development.

Returns data from mock_data.json, simulating the Retaguarda DataSnap
responses without any network calls.
"""

import asyncio
import json
import uuid
from decimal import Decimal
from pathlib import Path

from app.services.erp.schemas import (
    BillingPayloadSchema,
    CondominiumSyncSchema,
    PaymentStatusSchema,
    ResidentSchema,
    SubmitResultItem,
    SubmitResultSchema,
    UserSyncSchema,
)

_DATA_FILE = Path(__file__).parent / "mock_data.json"


class MockERPClient:
    """ERP client for development — uses local JSON data."""

    def __init__(self) -> None:
        with open(_DATA_FILE, encoding="utf-8") as f:
            self._data = json.load(f)

    async def get_users(self) -> list[UserSyncSchema]:
        return [UserSyncSchema(**u) for u in self._data["users"]]

    async def get_condominiums(self) -> list[CondominiumSyncSchema]:
        return [CondominiumSyncSchema(**c) for c in self._data["condominiums"]]

    async def get_residents(self, erp_code: str) -> list[ResidentSchema]:
        residents = self._data.get("residents", {}).get(erp_code, [])
        return [ResidentSchema(**r) for r in residents]

    async def get_payment_status(
        self, erp_code: str, reference_month: str
    ) -> list[PaymentStatusSchema]:
        key = f"{erp_code}_{reference_month}"
        statuses = self._data.get("payment_status", {}).get(key, [])
        return [PaymentStatusSchema(**s) for s in statuses]

    async def submit_billing(self, payload: BillingPayloadSchema) -> SubmitResultSchema:
        # Simulate network latency
        await asyncio.sleep(1)

        # Group items by unit_code
        units_seen: set[str] = set()
        results: list[SubmitResultItem] = []

        for item in payload.items:
            if item.unit_code in units_seen:
                continue
            units_seen.add(item.unit_code)

            # Check if quantity > 0 for any product on this unit
            unit_items = [i for i in payload.items if i.unit_code == item.unit_code]
            has_consumption = any(i.quantity > 0 for i in unit_items)

            if has_consumption:
                results.append(
                    SubmitResultItem(
                        unit_code=item.unit_code,
                        erp_invoice_id=f"MOCK-{uuid.uuid4().hex[:8].upper()}",
                        success=True,
                    )
                )
            else:
                results.append(
                    SubmitResultItem(
                        unit_code=item.unit_code,
                        success=False,
                        error="no_consumption",
                    )
                )

        submitted = sum(1 for r in results if r.success)
        skipped = sum(1 for r in results if not r.success)

        return SubmitResultSchema(
            success=True,
            submitted_count=submitted,
            skipped_count=skipped,
            results=results,
        )
