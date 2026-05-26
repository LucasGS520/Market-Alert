"""comparisons: separação entre snapshot de mercado e posição da referência

Revision ID: 016
Revises: 015
Create Date: 2026-05-22 00:00:00.000000

Contexto:
    O sistema passou a calcular o snapshot de mercado independentemente da
    disponibilidade da oferta de referência (MonitoredProduct). Quando a
    referência está indisponível, ranking e status ficam NULL no snapshot,
    mas min_price, max_price e average_price continuam sendo persistidos.

    reference_available (NOT NULL, default true) sinaliza explicitamente se
    a oferta de referência participou do snapshot, tornando NULLs em ranking
    e status interpretáveis sem ambiguidade.
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("comparisons", "status", nullable=True)
    op.alter_column("comparisons", "ranking", nullable=True)
    op.add_column(
        "comparisons",
        sa.Column("reference_available", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.execute("UPDATE comparisons SET status = 'competitive' WHERE status IS NULL")
    op.execute("UPDATE comparisons SET ranking = 1 WHERE ranking IS NULL")
    op.alter_column("comparisons", "status", nullable=False)
    op.alter_column("comparisons", "ranking", nullable=False)
    op.drop_column("comparisons", "reference_available")
