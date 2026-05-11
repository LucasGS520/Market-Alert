"""competitors: adiciona coluna status

Revision ID: 004
Revises: 003
Create Date: 2026-05-11 00:00:00.000000

Adiciona o campo status ao modelo Competitor, reutilizando o enum
product_status já existente. Permite registrar falhas de scraping no
concorrente sem corromper o status do produto monitorado principal.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "competitors",
        sa.Column(
            "status",
            postgresql.ENUM("active", "paused", "error", name="product_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
    )


def downgrade() -> None:
    op.drop_column("competitors", "status")
