"""notification_logs: alert types consolidados e reason_codes

Revision ID: 014
Revises: 013
Create Date: 2026-05-15 00:00:00.000000

Contexto:
    A camada de notificações estava gerando um push por evento técnico
    (status_change, ranking_change, market_price_drop) em vez de um push
    consolidado por fato de negócio. Esta migration introduz os novos
    alert types públicos e as colunas de suporte para auditoria.

    Novos alert types (uso ativo daqui em diante):
        price_drop_alert, price_rise_alert
        competitive_position_alert
        availability_alert
        error_alert

    Valores legados (ranking_change, status_change, market_price_drop, etc.)
    permanecem no enum para preservar linhas históricas; a aplicação não os
    escreve mais. Remoção pode ser feita em migration futura após limpeza de dados.

    Novas colunas:
        reason_codes    JSONB  — sinais técnicos que motivaram o alerta (auditoria)
        market_min_old  NUMERIC(12,2) — preço mínimo de mercado antes da comparação
        market_min_new  NUMERIC(12,2) — preço mínimo de mercado após a comparação
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Novos alert types no enum
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'price_drop_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'price_rise_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'competitive_position_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'availability_alert'"))
    op.execute(sa.text("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'error_alert'"))

    # 2. Colunas de suporte para alertas consolidados
    op.execute(sa.text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS reason_codes JSONB NULL"))
    op.execute(sa.text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS market_min_old NUMERIC(12,2) NULL"))
    op.execute(sa.text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS market_min_new NUMERIC(12,2) NULL"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE notification_logs DROP COLUMN IF EXISTS market_min_new"))
    op.execute(sa.text("ALTER TABLE notification_logs DROP COLUMN IF EXISTS market_min_old"))
    op.execute(sa.text("ALTER TABLE notification_logs DROP COLUMN IF EXISTS reason_codes"))

    # Valores adicionados ao enum não são removidos pelo mesmo motivo da migration 013:
    # PostgreSQL não suporta DROP VALUE nativamente; linhas históricas poderiam
    # referenciar esses valores. Em dev: DROP TYPE + recriar se necessário.
