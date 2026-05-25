"""notification_logs: adiciona market_alert ao enum notification_event_type

Revision ID: 017
Revises: 016
Create Date: 2026-05-22 00:00:00.000000

Contexto:
    O sistema passou a separar alertas de mercado de alertas da oferta de
    referência. Sinais como market_min_changed agora geram market_alert em vez
    de competitive_position_alert, preservando a semântica de cada classe de
    evento. ADD VALUE IF NOT EXISTS é idempotente no PostgreSQL 9.1+.
"""

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'market_alert'")


def downgrade() -> None:
    # PostgreSQL não permite remover valores de enum sem recriar o tipo.
    # Linhas com market_alert precisariam ser migradas antes de um downgrade real.
    pass
