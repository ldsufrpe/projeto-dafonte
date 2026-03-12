import pytest
from httpx import AsyncClient
from decimal import Decimal

from app.models.condominium import Condominium, CommissionType, OperatorAssignment
from app.models.unit import Unit
from app.models.product import Product, ProductPrice

@pytest.fixture
async def setup_billing_data(db_session, test_operator):
    # Create Condominium
    condo = Condominium(name="Test Condo", erp_code="TEST1", commission_type=CommissionType.fixed)
    db_session.add(condo)
    await db_session.commit()
    await db_session.refresh(condo)
    
    # Assign operator
    assignment = OperatorAssignment(user_id=test_operator.id, condominium_id=condo.id)
    db_session.add(assignment)
    
    # Create Unit
    unit1 = Unit(condominium_id=condo.id, unit_code="101", is_active=True)
    db_session.add(unit1)
    
    # Create Product
    prod = Product(name="Galão 20L", capacity_liters=20, sort_order=1, is_active=True)
    db_session.add(prod)
    await db_session.commit()
    await db_session.refresh(prod)
    
    # Create ProductPrice
    from datetime import date
    price = ProductPrice(product_id=prod.id, condominium_id=condo.id, valid_from=date(2026, 1, 1), unit_price=Decimal("15.00"), source="erp")
    db_session.add(price)
    
    await db_session.commit()
    await db_session.refresh(condo)
    await db_session.refresh(unit1)
    await db_session.refresh(prod)
    
    return {
        "condo": condo,
        "unit": unit1,
        "product": prod
    }

@pytest.mark.asyncio
async def test_get_billing_mesh(client: AsyncClient, operator_token, setup_billing_data):
    condo_id = setup_billing_data["condo"].id
    
    response = await client.get(
        f"/api/billing/{condo_id}/2026-03",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "rows" in data
    
    # The response should contain the generated billing items.
    assert len(data["rows"]) == 1
    assert data["rows"][0]["unit_code"] == "101"
    assert len(data["rows"][0]["items"]) == 1
    
    item = data["rows"][0]["items"][0]
    assert item["product_id"] == setup_billing_data["product"].id
    assert item["quantity"] == 0

@pytest.mark.asyncio
async def test_patch_billing_item(client: AsyncClient, operator_token, setup_billing_data):
    condo_id = setup_billing_data["condo"].id
    
    # First get the billing mesh to create the billing and items in DB
    mesh_response = await client.get(
        f"/api/billing/{condo_id}/2026-03",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    item_id = mesh_response.json()["rows"][0]["items"][0]["id"]
    
    # Now patch the quantity
    patch_response = await client.patch(
        f"/api/billing/item/{item_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"quantity": 5}
    )
    
    assert patch_response.status_code == 200
    patched_data = patch_response.json()
    assert patched_data["quantity"] == 5

@pytest.mark.asyncio
async def test_other_operator_forbidden(client: AsyncClient, operator_token, db_session):
    # Create condo not assigned to operator
    condo = Condominium(name="Other Condo", erp_code="OTHER", commission_type=CommissionType.fixed)
    db_session.add(condo)
    await db_session.commit()
    await db_session.refresh(condo)
    
    response = await client.get(
        f"/api/billing/{condo.id}/2026-03",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert response.status_code == 403
