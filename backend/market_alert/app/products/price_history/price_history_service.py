import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.products.price_history.price_model import PriceHistory


async def get_product_price_history(
    session: AsyncSession,
    monitored_id: uuid.UUID,
    limit: int = 200,
) -> list[PriceHistory]:
    resultado = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.monitored_id == monitored_id)
        .order_by(PriceHistory.collected_at.desc())
        .limit(limit)
    )
    return list(resultado.scalars().all())


async def get_competitor_price_history(
    session: AsyncSession,
    competitor_id: uuid.UUID,
    limit: int = 200,
) -> list[PriceHistory]:
    resultado = await session.execute(
        select(PriceHistory)
        .where(PriceHistory.competitor_id == competitor_id)
        .order_by(PriceHistory.collected_at.desc())
        .limit(limit)
    )
    return list(resultado.scalars().all())
