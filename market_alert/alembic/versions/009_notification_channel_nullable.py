"""notification_logs: tornar channel nullable para suportar registros skipped

Revision ID: 009
Revises: 008
Create Date: 2026-05-12 00:00:00.000000

Mudancas:
- notification_logs.channel: NOT NULL -> NULL
  Permite registrar delivery_status='skipped' quando nenhum canal esta configurado,
  mantendo auditabilidade completa sem precisar criar um canal ficticio.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("notification_logs", "channel", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM notification_logs WHERE channel IS NULL")
    op.alter_column("notification_logs", "channel", nullable=False)
