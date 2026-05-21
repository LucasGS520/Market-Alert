"""monitored_products: adiciona last_successful_collection_at

Revision ID: 015
Revises: 014
Create Date: 2026-05-18 00:00:00.000000

Contexto:
    O sistema não distinguia "última tentativa de coleta" de "última coleta
    bem-sucedida". A UI mostrava current_price como "preço atual" mesmo quando
    o status do produto era "error" ou "unavailable", induzindo o usuário a
    interpretar um dado obsoleto como dado atual.

    Este campo é setado exclusivamente no path de sucesso de collect_product()
    e exposto no schema como parte do campo computado is_price_stale.
"""

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monitored_products",
        sa.Column("last_successful_collection_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("monitored_products", "last_successful_collection_at")
