import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_admin):
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin_test", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

@pytest.mark.asyncio
async def test_login_failure(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin_test", "password": "wrongpassword"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_rbac_admin_only(client: AsyncClient, operator_token):
    # Try to access admin-only endpoint
    response = await client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    # The endpoint might not exist as GET /api/users, but /api/condominiums/{id}/commission-config is admin only
    # Let's test commission config since we know it exists
    response = await client.put(
        "/api/finance/condominiums/1/commission-config",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"commission_type": "fixed", "commission_value": 100}
    )
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_rbac_admin_access(client: AsyncClient, admin_token, db_session):
    # Create condo first
    from app.models.condominium import Condominium, CommissionType
    condo = Condominium(name="Test Condo", erp_code="TEST1", commission_type=CommissionType.fixed)
    db_session.add(condo)
    await db_session.commit()
    await db_session.refresh(condo)
    
    response = await client.put(
        f"/api/finance/condominiums/{condo.id}/commission-config",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"commission_type": "percent", "commission_value": 15}
    )
    assert response.status_code == 200
    assert response.json()["commission_type"] == "percent"
