import pytest
from httpx import AsyncClient

from app.models.condominium import Condominium, CommissionType

@pytest.fixture
async def setup_finance_data(db_session):
    condo = Condominium(name="Condo Finance", erp_code="FIN1", commission_type=CommissionType.fixed, commission_value=500.0)
    db_session.add(condo)
    await db_session.commit()
    await db_session.refresh(condo)
    return {"condo": condo}

@pytest.mark.asyncio
async def test_get_commissions(client: AsyncClient, admin_token, setup_finance_data):
    condo_id = setup_finance_data["condo"].id
    response = await client.get(
        f"/api/finance/commission/{condo_id}/2026-03",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["condominium_id"] == condo_id
    assert data["commission_type"] == "fixed"
    assert data["commission_value"] == "500.00"

@pytest.mark.asyncio
async def test_update_commission_config(client: AsyncClient, admin_token, setup_finance_data):
    condo_id = setup_finance_data["condo"].id
    response = await client.put(
        f"/api/finance/condominiums/{condo_id}/commission-config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"commission_type": "percent", "commission_value": 15.0}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["commission_type"] == "percent"
    assert float(data["commission_value"]) == 15.0

@pytest.mark.asyncio
async def test_get_operator_performance(client: AsyncClient, operator_token):
    response = await client.get(
        "/api/finance/operator-performance/2026-03",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_operator_forbidden_commission_config(client: AsyncClient, operator_token, setup_finance_data):
    condo_id = setup_finance_data["condo"].id
    response = await client.put(
        f"/api/finance/condominiums/{condo_id}/commission-config",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"commission_type": "percent", "commission_value": 15.0}
    )
    assert response.status_code == 403
