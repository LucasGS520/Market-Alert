"""notification_logs: remover coluna channel e enum notification_channel

Revision ID: 012
Revises: 011
Create Date: 2026-05-14 00:00:00.000000

Problema:
    A camada de notificações suportava múltiplos canais (ntfy, telert), gerando um
    log por canal por tentativa. Com a consolidação para ntfy como único provedor,
    a coluna channel e o enum notification_channel se tornam obsoletos.
    Além disso, o índice único dependia de channel como parte da chave.

Correção:
    Remove a coluna channel, o enum notification_channel e o índice antigo.
    Cria novo índice parcial único em (comparison_id, event_type) para garantir
    idempotência de entrega sem depender do canal.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notification_comparison_event_channel")
    op.execute("ALTER TABLE notification_logs DROP COLUMN IF EXISTS channel")
    op.execute("DROP TYPE IF EXISTS notification_channel")
    op.execute("""
        CREATE UNIQUE INDEX uq_notification_comparison_event
        ON notification_logs (comparison_id, event_type)
        WHERE comparison_id IS NOT NULL AND delivery_status = 'sent'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notification_comparison_event")
    op.execute("CREATE TYPE notification_channel AS ENUM ('ntfy', 'telert')")
    op.execute("""
        ALTER TABLE notification_logs
        ADD COLUMN channel notification_channel NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_notification_comparison_event_channel
        ON notification_logs (comparison_id, event_type, channel)
        WHERE comparison_id IS NOT NULL AND delivery_status = 'sent'
    """)
