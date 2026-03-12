import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.models.condominium import Condominium, CommissionType
from app.core.security import hash_password
from app.services.erp.factory import get_erp_client
from app.services.erp.mock_client import MockERPClient

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Override ERP client to always use mock in tests
    app.dependency_overrides[get_erp_client] = lambda: MockERPClient()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
        
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def test_admin(db_session):
    admin = User(
        username="admin_test",
        hashed_password=hash_password("password123"),
        full_name="Admin Test",
        role=UserRole.admin,
        is_active=True
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin

@pytest_asyncio.fixture
async def test_operator(db_session):
    operator = User(
        username="operator_test",
        hashed_password=hash_password("password123"),
        full_name="Operator Test",
        role=UserRole.operator,
        is_active=True
    )
    db_session.add(operator)
    await db_session.commit()
    await db_session.refresh(operator)
    return operator

@pytest_asyncio.fixture
async def admin_token(client, test_admin):
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin_test", "password": "password123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest_asyncio.fixture
async def operator_token(client, test_operator):
    response = await client.post(
        "/api/auth/login",
        json={"username": "operator_test", "password": "password123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]
