"""ERP client factory.

Returns the appropriate ERP client based on ERP_MODE setting.
Use as a FastAPI dependency: `erp = Depends(get_erp_client)`.
"""

from app.core.config import settings
from app.services.erp.base import ERPClientBase
from app.services.erp.mock_client import MockERPClient


def get_erp_client() -> ERPClientBase:
    """Return the ERP client for the current mode."""
    if settings.ERP_MODE == "datasnap":
        raise NotImplementedError(
            "DataSnap client será implementado em sprint futuro (Sprint 4b). "
            "Use ERP_MODE=mock para desenvolvimento."
        )
    return MockERPClient()
