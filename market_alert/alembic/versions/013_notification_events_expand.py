"""notification_logs: expandir taxonomia de eventos e adicionar campos de ranking/concorrente

Revision ID: 013
Revises: 012
Create Date: 2026-05-14 00:00:00.000000

Contexto:
    A taxonomia anterior cobria apenas 3 eventos (price_drop, price_rise, status_change).
    Esta migration adiciona 7 novos tipos de evento divididos em dois tiers de prioridade:

    Tier 1 — produto monitorado:
        ranking_change, product_unavailable, product_available

    Tier 2 — mercado / concorrentes:
        market_price_drop, market_price_rise, competitor_unavailable, competitor_available

    Também adiciona as colunas old_ranking, new_ranking (para eventos de ranking) e
    competitor_id FK (para eventos de concorrentes).

Nota sobre ALTER TYPE ADD VALUE:
    Em PostgreSQL >= 12, ADD VALUE pode ser executado dentro de uma transação.
    Em versões anteriores, é necessário autocommit. A migration usa op.execute() que
    é seguro para PG >= 12 (padrão em qualquer instalação recente).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Adicionar novos valores ao enum notification_event_type
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'ranking_change'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'product_unavailable'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'product_available'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'market_price_drop'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'market_price_rise'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'competitor_unavailable'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'competitor_available'"))

    # 2. Campos de ranking (tier 1: ranking_change)
    op.execute(sa.text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS old_ranking INTEGER NULL"))
    op.execute(sa.text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS new_ranking INTEGER NULL"))

    # 3. FK para concorrente (tier 2: competitor_unavailable, competitor_available)
    op.execute(sa.text("""
        ALTER TABLE notification_logs
        ADD COLUMN IF NOT EXISTS competitor_id UUID NULL
        REFERENCES competitors(id) ON DELETE SET NULL
    """))


def downgrade() -> None:
    # Remove as colunas adicionadas
    op.execute(sa.text("ALTER TABLE notification_logs DROP COLUMN IF EXISTS competitor_id"))
    op.execute(sa.text("ALTER TABLE notification_logs DROP COLUMN IF EXISTS new_ranking"))
    op.execute(sa.text("ALTER TABLE notification_logs DROP COLUMN IF EXISTS old_ranking"))

    # PostgreSQL não suporta REMOVE VALUE de enum nativamente.
    # Para reverter completamente, seria necessário recriar o tipo e reescrever a coluna.
    # Como operação destrutiva de dados seria necessária, o downgrade apenas documenta
    # que os valores não utilizados permanecem no enum.
    # Em ambiente de desenvolvimento, use: DROP TYPE + recriar se necessário.
