"""notification_logs: novos alert types orientados a impacto competitivo + skip_reason

Revision ID: 019
Revises: 018
Create Date: 2026-05-26 00:00:00.000000

Contexto:
    O pipeline de notificações priorizava variação de preço da referência
    (price_drop_alert, price_rise_alert) acima de sinais competitivos.
    Esta migration prepara o enum para a nova hierarquia de alertas orientada
    a impacto competitivo:

        competitive_threat_alert      — posição do usuário piorou (ranking, status, gap)
        competitive_opportunity_alert — posição melhorou ou mercado ficou menos agressivo
        market_movement_alert         — mercado moveu sem impacto direto na posição
        competitor_movement_alert     — concorrente específico mudou de posição relevante
        reference_availability_alert  — disponibilidade da oferta de referência mudou
        competitor_availability_alert — disponibilidade de concorrente mudou
        collection_health_alert       — problemas operacionais de coleta

    Tipos anteriores (price_drop_alert, price_rise_alert, competitive_position_alert,
    market_alert, availability_alert, error_alert) permanecem ativos para linhas
    históricas e fallback; a aplicação migrará gradualmente para os novos tipos.

    Nova coluna:
        skip_reason  VARCHAR(50)  — motivo de supressão de entrega quando
                                   delivery_status = 'skipped'
                                   Exemplos: insufficient_quorum, degraded_run,
                                   manual_run, cooldown_active, deduplicated
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Novos alert types no enum (ADD VALUE não pode rodar dentro de transação
    #    explícita no PostgreSQL; op.execute com text é equivalente ao DDL direto)
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'competitive_threat_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'competitive_opportunity_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'market_movement_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'competitor_movement_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'reference_availability_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'competitor_availability_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'collection_health_alert'"))

    # 2. Campo de auditoria de supressão
    op.execute(sa.text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS skip_reason VARCHAR(50) NULL"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE notification_logs DROP COLUMN IF EXISTS skip_reason"))

    # Valores adicionados ao enum não são removidos: PostgreSQL não suporta
    # DROP VALUE nativamente e linhas históricas poderiam referenciar esses valores.
    # Em ambiente de desenvolvimento: DROP TYPE + recriar se necessário.
