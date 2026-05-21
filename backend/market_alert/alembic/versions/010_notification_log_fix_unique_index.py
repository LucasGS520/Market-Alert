"""notification_logs: corrigir indice unico para excluir linhas de status failed

Revision ID: 010
Revises: 009
Create Date: 2026-05-12 00:00:00.000000

Problema:
    O indice uq_notification_comparison_event_channel era parcial apenas em
    comparison_id IS NOT NULL. Isso impedia INSERT de novas linhas com
    delivery_status='failed' num segundo retry, pois a primeira tentativa
    falha ja havia inserido uma linha com o mesmo (comparison_id, event_type,
    channel), gerando IntegrityError por violacao de unique constraint.

Correcao:
    Adiciona condicao AND delivery_status = 'sent' ao WHERE do indice parcial.
    Linhas 'failed' (tentativas de retry) nao estao mais sujeitas ao unique,
    permitindo multiplas entradas por tentativa. A garantia de idempotencia
    permanece: no maximo uma linha 'sent' por (comparison_id, event_type, channel).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notification_comparison_event_channel")
    op.execute("""
        CREATE UNIQUE INDEX uq_notification_comparison_event_channel
        ON notification_logs (comparison_id, event_type, channel)
        WHERE comparison_id IS NOT NULL AND delivery_status = 'sent'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notification_comparison_event_channel")
    op.execute("""
        CREATE UNIQUE INDEX uq_notification_comparison_event_channel
        ON notification_logs (comparison_id, event_type, channel)
        WHERE comparison_id IS NOT NULL
    """)
