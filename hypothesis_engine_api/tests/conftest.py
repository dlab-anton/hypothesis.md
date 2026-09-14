import os
import re
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from typing import AsyncGenerator

from app.core.auth_context import AuthContext
from app.db.models.base_class import Base
from app.api.deps import get_db_session
from app.core.security import get_api_key
from app.main import app
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/hypothesis_engine_test",
)

TEST_API_KEY = "test-api-key-for-testing"
TEST_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    async_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield async_engine
    await async_engine.dispose()


@pytest.fixture(scope="session")
async def setup_database(engine: AsyncEngine):
    """Create tables at session start, drop at end.
    NOT autouse — only triggered when a test requests db_session or client."""
    target = make_url(TEST_DATABASE_URL)
    if target.host not in {"localhost", "127.0.0.1"} or not re.fullmatch(
        r"hypothesis_(?:writeback|contract)_[0-9a-f]{32}", target.database or ""
    ):
        pytest.fail("Database tests require the runner-created UUID database on loopback")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception:
        pass


@pytest.fixture
async def db_session(engine: AsyncEngine, setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped DB session with transaction rollback for test isolation."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        yield session
        await session.close()
        await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient wired to the FastAPI app with overridden deps."""

    async def override_get_db():
        yield db_session

    async def override_get_api_key():
        return AuthContext(tenant_id=TEST_TENANT_ID, is_master=False)

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_api_key] = override_get_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
