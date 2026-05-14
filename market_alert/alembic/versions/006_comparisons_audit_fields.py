"""comparisons: campos de auditoria de rodada

Revision ID: 006
Revises: 005
Create Date: 2026-05-11 00:00:00.000000

Mudanças:
- Cria enum run_status (complete, partial, expired, no_competitors, manual)
- Adiciona colunas em comparisons:
    run_id                 VARCHAR(36)    NULL
    run_status             run_status     NULL
    product_price          NUMERIC(12,2)  NULL
    participants_count     INTEGER        NULL
    valid_competitors_count   INTEGER     NULL
    ignored_competitors_count INTEGER     NULL

Colunas antigas recebem NULL (sem backfill).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum não é transacional no PG — executa fora do bloco DDL
    op.execute(
        "CREATE TYPE run_status AS ENUM "
        "('complete', 'partial', 'expired', 'no_competitors', 'manual')"
    )

    op.add_column("comparisons", sa.Column("run_id", sa.String(36), nullable=True))
    op.add_column(
        "comparisons",
        sa.Column("run_status", sa.Enum(
            "complete", "partial", "expired", "no_competitors", "manual",
            name="run_status", create_type=False,
        ), nullable=True),
    )
    op.add_column("comparisons", sa.Column("product_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("comparisons", sa.Column("participants_count", sa.Integer(), nullable=True))
    op.add_column("comparisons", sa.Column("valid_competitors_count", sa.Integer(), nullable=True))
    op.add_column("comparisons", sa.Column("ignored_competitors_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("comparisons", "ignored_competitors_count")
    op.drop_column("comparisons", "valid_competitors_count")
    op.drop_column("comparisons", "participants_count")
    op.drop_column("comparisons", "product_price")
    op.drop_column("comparisons", "run_status")
    op.drop_column("comparisons", "run_id")

    op.execute("DROP TYPE run_status")
