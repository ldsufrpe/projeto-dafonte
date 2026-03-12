"""Abstract ERP client protocol.

Any ERP integration (mock, DataSnap, future) must implement this protocol.
Using Protocol (structural subtyping) instead of ABC so implementations
don't need to inherit — just match the method signatures.
"""

from typing import Protocol, runtime_checkable

from app.services.erp.schemas import (
    BillingPayloadSchema,
    CondominiumSyncSchema,
    PaymentStatusSchema,
    ResidentSchema,
    SubmitResultSchema,
    UserSyncSchema,
)


@runtime_checkable
class ERPClientBase(Protocol):
    async def get_users(self) -> list[UserSyncSchema]: ...

    async def get_condominiums(self) -> list[CondominiumSyncSchema]: ...

    async def get_residents(self, erp_code: str) -> list[ResidentSchema]: ...

    async def get_payment_status(
        self, erp_code: str, reference_month: str
    ) -> list[PaymentStatusSchema]: ...

    async def submit_billing(self, payload: BillingPayloadSchema) -> SubmitResultSchema: ...
