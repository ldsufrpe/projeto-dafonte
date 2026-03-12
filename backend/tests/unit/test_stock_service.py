import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.stock import _compute_product_stats

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.mark.asyncio
async def test_compute_product_stats_clean_month(mock_db):
    # mock_db.execute will be called 4 times:
    # 1. entradas this month
    # 2. entradas before this month
    # 3. consumo this month
    # 4. consumo before this month
    
    mock_db.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value=100)),  # entradas
        MagicMock(scalar=MagicMock(return_value=50)),   # entradas_prev
        MagicMock(scalar=MagicMock(return_value=30)),   # consumo
        MagicMock(scalar=MagicMock(return_value=40)),   # consumo_prev
    ]
    
    saldo_anterior, entradas, consumo, saldo_atual = await _compute_product_stats(
        mock_db, condominium_id=1, product_id=1, reference_month="2026-03"
    )
    
    # saldo_anterior = entradas_prev - consumo_prev = 50 - 40 = 10
    assert saldo_anterior == 10
    assert entradas == 100
    assert consumo == 30
    # saldo_atual = saldo_anterior + entradas - consumo = 10 + 100 - 30 = 80
    assert saldo_atual == 80

@pytest.mark.asyncio
async def test_compute_product_stats_negative_stock(mock_db):
    mock_db.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value=10)),  # entradas
        MagicMock(scalar=MagicMock(return_value=0)),   # entradas_prev
        MagicMock(scalar=MagicMock(return_value=50)),  # consumo
        MagicMock(scalar=MagicMock(return_value=0)),   # consumo_prev
    ]
    
    saldo_anterior, entradas, consumo, saldo_atual = await _compute_product_stats(
        mock_db, condominium_id=1, product_id=1, reference_month="2026-03"
    )
    
    assert saldo_anterior == 0
    assert entradas == 10
    assert consumo == 50
    assert saldo_atual == -40

@pytest.mark.asyncio
async def test_compute_product_stats_none_values(mock_db):
    # Test when scalar() returns None (should coalesce to 0)
    mock_db.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value=None)),
        MagicMock(scalar=MagicMock(return_value=None)),
        MagicMock(scalar=MagicMock(return_value=None)),
        MagicMock(scalar=MagicMock(return_value=None)),
    ]
    
    saldo_anterior, entradas, consumo, saldo_atual = await _compute_product_stats(
        mock_db, condominium_id=1, product_id=1, reference_month="2026-03"
    )
    
    assert saldo_anterior == 0
    assert entradas == 0
    assert consumo == 0
    assert saldo_atual == 0
