from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from ..core.config import settings

pool_options = (
    {"poolclass": NullPool}
    if settings.ENVIRONMENT == "production"
    else {"pool_size": 20, "max_overflow": 30, "pool_timeout": 30}
)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    hide_parameters=True,
    pool_pre_ping=True,
    **pool_options,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
