"""produtos: normalização de URL e expansão do enum de status

Revision ID: 005
Revises: 004
Create Date: 2026-05-11 00:00:00.000000

Mudanças:
- Adiciona valores pending, unsupported, unavailable ao enum product_status
- Renomeia url → url_original em monitored_products e competitors
- Adiciona coluna url_normalized em ambas as tabelas (populada a partir de url_original)
- Remove unicidade em url_original; adiciona unicidade em url_normalized
- Muda server_default de status para 'pending' em ambas as tabelas
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Novos valores do enum (ADD VALUE não é transacional no PG < 12; executa fora do bloco DDL)
    op.execute("ALTER TYPE product_status ADD VALUE IF NOT EXISTS 'pending'")
    op.execute("ALTER TYPE product_status ADD VALUE IF NOT EXISTS 'unsupported'")
    op.execute("ALTER TYPE product_status ADD VALUE IF NOT EXISTS 'unavailable'")

    # 2. monitored_products ────────────────────────────────────────────────────
    # Renomeia url → url_original
    op.alter_column("monitored_products", "url", new_column_name="url_original")

    # Adiciona url_normalized (nullable temporariamente para população)
    op.add_column(
        "monitored_products",
        sa.Column("url_normalized", sa.String(2048), nullable=True),
    )

    # Popula url_normalized a partir de url_original (strip tracking params via SQL básico)
    # Normalização completa é responsabilidade da camada de serviço; aqui usamos o valor bruto
    # como ponto de partida seguro para dados existentes
    op.execute("UPDATE monitored_products SET url_normalized = url_original")

    op.alter_column("monitored_products", "url_normalized", nullable=False)

    # Remove unicidade antiga (gerada automaticamente pelo unique=True na coluna url)
    op.drop_constraint("monitored_products_url_key", "monitored_products", type_="unique")

    # Cria unicidade em url_normalized
    op.create_unique_constraint("uq_monitored_url_normalized", "monitored_products", ["url_normalized"])

    # Muda server_default do status
    op.alter_column(
        "monitored_products",
        "status",
        server_default="pending",
        existing_type=sa.Enum(
            "pending", "active", "paused", "error", "unsupported", "unavailable",
            name="product_status",
        ),
        existing_nullable=False,
    )

    # 3. competitors ──────────────────────────────────────────────────────────
    # Renomeia url → url_original
    op.alter_column("competitors", "url", new_column_name="url_original")

    # Adiciona url_normalized
    op.add_column(
        "competitors",
        sa.Column("url_normalized", sa.String(2048), nullable=True),
    )
    op.execute("UPDATE competitors SET url_normalized = url_original")
    op.alter_column("competitors", "url_normalized", nullable=False)

    # Remove unicidade antiga e cria nova em (monitored_id, url_normalized)
    op.drop_constraint("uq_competitor_monitored_url", "competitors", type_="unique")
    op.create_unique_constraint(
        "uq_competitor_monitored_url_normalized",
        "competitors",
        ["monitored_id", "url_normalized"],
    )

    # Muda server_default do status
    op.alter_column(
        "competitors",
        "status",
        server_default="pending",
        existing_type=sa.Enum(
            "pending", "active", "paused", "error", "unsupported", "unavailable",
            name="product_status",
        ),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Nota: valores adicionados ao enum product_status (pending, unsupported, unavailable)
    # não podem ser removidos no PostgreSQL sem recriar o tipo. O downgrade reverte apenas
    # as mudanças de coluna e constraints.

    # competitors ─────────────────────────────────────────────────────────────
    op.alter_column(
        "competitors",
        "status",
        server_default="active",
        existing_type=sa.Enum(
            "pending", "active", "paused", "error", "unsupported", "unavailable",
            name="product_status",
        ),
        existing_nullable=False,
    )
    op.drop_constraint("uq_competitor_monitored_url_normalized", "competitors", type_="unique")
    op.create_unique_constraint("uq_competitor_monitored_url", "competitors", ["monitored_id", "url_original"])
    op.drop_column("competitors", "url_normalized")
    op.alter_column("competitors", "url_original", new_column_name="url")

    # monitored_products ──────────────────────────────────────────────────────
    op.alter_column(
        "monitored_products",
        "status",
        server_default="active",
        existing_type=sa.Enum(
            "pending", "active", "paused", "error", "unsupported", "unavailable",
            name="product_status",
        ),
        existing_nullable=False,
    )
    op.drop_constraint("uq_monitored_url_normalized", "monitored_products", type_="unique")
    op.create_unique_constraint("monitored_products_url_key", "monitored_products", ["url_original"])
    op.drop_column("monitored_products", "url_normalized")
    op.alter_column("monitored_products", "url_original", new_column_name="url")
