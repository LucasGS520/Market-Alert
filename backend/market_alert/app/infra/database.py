from collections.abc import AsyncGenerator

from sqlalchemy.orm import configure_mappers
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.infra.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def import_all_models() -> None:
    """Load every ORM model so string relationships are resolvable."""
    from app.comparison import comparison_model  # noqa: F401
    from app.notifications import notifications_model  # noqa: F401
    from app.products.competitor import competitor_model  # noqa: F401
    from app.products.monitored import monitored_model  # noqa: F401
    from app.products.price_history import price_model  # noqa: F401


def configure_orm_mappers() -> None:
    """Fail fast if an ORM relationship target was not imported."""
    import_all_models()
    configure_mappers()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
