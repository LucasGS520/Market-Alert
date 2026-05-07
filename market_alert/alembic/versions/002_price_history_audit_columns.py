"""price_history audit columns

Revision ID: 002
Revises: 001
Create Date: 2026-05-07 00:00:00.000000

Adiciona colunas de auditoria ao price_history para preservar o contexto
técnico de cada coleta: título, vendedor, moeda, método de extração e
nível de confiança reportado pelo market_scraper.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("price_history", sa.Column("title", sa.String(512), nullable=True))
    op.add_column("price_history", sa.Column("seller", sa.String(512), nullable=True))
    op.add_column("price_history", sa.Column("currency", sa.String(8), nullable=True))
    op.add_column("price_history", sa.Column("extraction_method", sa.String(64), nullable=True))
    op.add_column("price_history", sa.Column("confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("price_history", "confidence")
    op.drop_column("price_history", "extraction_method")
    op.drop_column("price_history", "currency")
    op.drop_column("price_history", "seller")
    op.drop_column("price_history", "title")
