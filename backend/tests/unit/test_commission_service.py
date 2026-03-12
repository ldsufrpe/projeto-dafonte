from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.condominium import Condominium, CommissionType, CommissionRate
from app.models.billing import Billing, BillingItem, BillingStatus
from app.api.finance import _calc_commission

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.mark.asyncio
async def test_calc_commission_fixed(mock_db):
    condo = Condominium(
        id=1,
        commission_type=CommissionType.fixed,
        commission_value=Decimal("150.00")
    )
    
    # Mock total_received query
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = Decimal("1000.00")
    mock_db.execute.return_value = mock_result
    
    total_received, commission = await _calc_commission(mock_db, condo, "2026-03")
    assert total_received == Decimal("1000.00")
    assert commission == Decimal("150.00")

@pytest.mark.asyncio
async def test_calc_commission_percent(mock_db):
    condo = Condominium(
        id=1,
        commission_type=CommissionType.percent,
        commission_value=Decimal("10.00")  # 10%
    )
    
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = Decimal("2000.00")
    mock_db.execute.return_value = mock_result
    
    total_received, commission = await _calc_commission(mock_db, condo, "2026-03")
    assert total_received == Decimal("2000.00")
    assert commission == Decimal("200.00")

@pytest.mark.asyncio
async def test_calc_commission_per_unit(mock_db):
    condo = Condominium(
        id=1,
        commission_type=CommissionType.per_unit,
        commission_value=None
    )
    
    # We need to mock 3 calls to db.execute:
    # 1. total_received
    mock_result_total = MagicMock()
    mock_result_total.scalar_one.return_value = Decimal("500.00")
    
    # 2. rates_q
    mock_result_rates = MagicMock()
    rate1 = CommissionRate(product_id=1, value_per_unit=Decimal("2.00"))
    rate2 = CommissionRate(product_id=2, value_per_unit=Decimal("3.00"))
    mock_result_rates.scalars().all.return_value = [rate1, rate2]
    
    # 3. qty_q
    mock_result_qty = MagicMock()
    # (product_id, qty)
    mock_result_qty.all.return_value = [(1, 10), (2, 5)]
    
    mock_db.execute.side_effect = [mock_result_total, mock_result_rates, mock_result_qty]
    
    total_received, commission = await _calc_commission(mock_db, condo, "2026-03")
    assert total_received == Decimal("500.00")
    # Commission: (10 * 2.00) + (5 * 3.00) = 20.00 + 15.00 = 35.00
    assert commission == Decimal("35.00")
