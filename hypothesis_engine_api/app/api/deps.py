from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import SessionLocal


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
