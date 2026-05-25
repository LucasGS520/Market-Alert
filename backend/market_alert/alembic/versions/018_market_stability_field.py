"""monitored_products: remove consecutive_unchanged (morto), adiciona last_market_changed_at

Revision ID: 018
Revises: 017
Create Date: 2026-05-25 00:00:00.000000

Contexto:
    consecutive_unchanged estava definido no modelo mas nunca foi lido nem
    escrito em nenhum ponto do codebase — campo morto, removido.

    last_market_changed_at registra quando o snapshot de mercado mudou pela
    última vez (via comparison_task). Permite que classify_stability() use
    a volatilidade do mercado completo (e não só da referência) para definir
    o intervalo de coleta.
"""

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("monitored_products", "consecutive_unchanged")
    op.add_column(
        "monitored_products",
        sa.Column("last_market_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("monitored_products", "last_market_changed_at")
    op.add_column(
        "monitored_products",
        sa.Column("consecutive_unchanged", sa.Integer(), nullable=False, server_default="0"),
    )
