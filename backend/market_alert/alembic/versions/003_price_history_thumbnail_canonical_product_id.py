"""price_history: thumbnail_url, canonical_url, product_id

Revision ID: 003
Revises: 002
Create Date: 2026-05-08 00:00:00.000000

Adiciona ao price_history os metadados de produto definidos no contrato v1
do market_scraper: imagem principal do anúncio, URL canônica e ID do produto
no marketplace (ex: MLB123456789).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("price_history", sa.Column("thumbnail_url", sa.String(2048), nullable=True))
    op.add_column("price_history", sa.Column("canonical_url", sa.String(2048), nullable=True))
    op.add_column("price_history", sa.Column("product_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("price_history", "product_id")
    op.drop_column("price_history", "canonical_url")
    op.drop_column("price_history", "thumbnail_url")
