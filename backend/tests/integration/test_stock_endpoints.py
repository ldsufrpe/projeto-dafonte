import pytest
from httpx import AsyncClient

from app.models.condominium import Condominium, OperatorAssignment
from app.models.product import Product

@pytest.fixture
async def setup_stock_data(db_session, test_operator):
    condo = Condominium(name="Condo Stock", erp_code="STK1")
    db_session.add(condo)
    await db_session.commit()
    await db_session.refresh(condo)
    
    asgn = OperatorAssignment(condominium_id=condo.id, user_id=test_operator.id)
    db_session.add(asgn)
    
    prod = Product(name="Galão 10L", capacity_liters=10, sort_order=1, is_active=True)
    db_session.add(prod)
    
    await db_session.commit()
    await db_session.refresh(prod)
    return {"condo": condo, "product": prod}

@pytest.mark.asyncio
async def test_get_stock_overview(client: AsyncClient, operator_token, setup_stock_data):
    condo_id = setup_stock_data["condo"].id
    response = await client.get(
        f"/api/stock/{condo_id}/2026-03",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "products" in data
    assert len(data["products"]) == 1
    assert data["products"][0]["product_id"] == setup_stock_data["product"].id

@pytest.mark.asyncio
async def test_create_and_delete_stock_entry(client: AsyncClient, operator_token, setup_stock_data):
    condo_id = setup_stock_data["condo"].id
    prod_id = setup_stock_data["product"].id
    
    # Create
    response = await client.post(
        "/api/stock/entries",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "condominium_id": condo_id,
            "product_id": prod_id,
            "reference_month": "2026-03",
            "quantity": 50,
            "entry_type": "purchase",
            "notes": "Test entry"
        }
    )
    assert response.status_code == 201
    entry_id = response.json()["id"]
    
    # Update
    response_update = await client.put(
        f"/api/stock/entries/{entry_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"quantity": 60}
    )
    assert response_update.status_code == 200
    assert response_update.json()["quantity"] == 60
    
    # Delete
    response_del = await client.delete(
        f"/api/stock/entries/{entry_id}",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert response_del.status_code == 204
