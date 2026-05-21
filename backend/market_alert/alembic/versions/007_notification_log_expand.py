"""notification_logs: expandir para tentativa de entrega

Revision ID: 007
Revises: 006
Create Date: 2026-05-11 00:00:00.000000

Mudancas:
- Cria enum delivery_status (pending, sent, failed, skipped)
- Adiciona colunas em notification_logs:
    comparison_id      UUID           NULL  FK -> comparisons(id) SET NULL
    delivery_status    delivery_status NOT NULL (backfill 'sent' em registros antigos)
    title              TEXT           NULL
    error_message      TEXT           NULL
    attempt_count      INTEGER        NOT NULL default 1
    old_price          NUMERIC(12,2)  NULL
    new_price          NUMERIC(12,2)  NULL
    old_status         VARCHAR(50)    NULL
    new_status         VARCHAR(50)    NULL
    run_id             VARCHAR(36)    NULL
    run_status         VARCHAR(50)    NULL
    participants_count INTEGER        NULL
- Cria FK fk_notification_logs_comparison_id
- Cria indice parcial uq_notification_comparison_event_channel
  (comparison_id, event_type, channel) WHERE comparison_id IS NOT NULL
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE delivery_status AS ENUM ('pending', 'sent', 'failed', 'skipped')")

    op.add_column(
        "notification_logs",
        sa.Column("comparison_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "notification_logs",
        sa.Column(
            "delivery_status",
            postgresql.ENUM("pending", "sent", "failed", "skipped", name="delivery_status", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("notification_logs", sa.Column("title", sa.Text(), nullable=True))
    op.add_column("notification_logs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column(
        "notification_logs",
        sa.Column("attempt_count", sa.Integer(), nullable=True, server_default="1"),
    )
    op.add_column("notification_logs", sa.Column("old_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("notification_logs", sa.Column("new_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("notification_logs", sa.Column("old_status", sa.String(50), nullable=True))
    op.add_column("notification_logs", sa.Column("new_status", sa.String(50), nullable=True))
    op.add_column("notification_logs", sa.Column("run_id", sa.String(36), nullable=True))
    op.add_column("notification_logs", sa.Column("run_status", sa.String(50), nullable=True))
    op.add_column("notification_logs", sa.Column("participants_count", sa.Integer(), nullable=True))

    # Registros anteriores foram gravados apenas em caso de sucesso: backfill como 'sent'.
    op.execute("UPDATE notification_logs SET delivery_status = 'sent', attempt_count = 1 WHERE delivery_status IS NULL")

    op.alter_column("notification_logs", "delivery_status", nullable=False)
    op.alter_column("notification_logs", "attempt_count", nullable=False)

    op.create_foreign_key(
        "fk_notification_logs_comparison_id",
        "notification_logs",
        "comparisons",
        ["comparison_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("""
        CREATE UNIQUE INDEX uq_notification_comparison_event_channel
        ON notification_logs (comparison_id, event_type, channel)
        WHERE comparison_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notification_comparison_event_channel")
    op.drop_constraint("fk_notification_logs_comparison_id", "notification_logs", type_="foreignkey")
    op.drop_column("notification_logs", "participants_count")
    op.drop_column("notification_logs", "run_status")
    op.drop_column("notification_logs", "run_id")
    op.drop_column("notification_logs", "new_status")
    op.drop_column("notification_logs", "old_status")
    op.drop_column("notification_logs", "new_price")
    op.drop_column("notification_logs", "old_price")
    op.drop_column("notification_logs", "attempt_count")
    op.drop_column("notification_logs", "error_message")
    op.drop_column("notification_logs", "title")
    op.drop_column("notification_logs", "delivery_status")
    op.drop_column("notification_logs", "comparison_id")
    op.execute("DROP TYPE IF EXISTS delivery_status")
