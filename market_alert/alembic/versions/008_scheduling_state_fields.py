"""monitored_products: campos de estado operacional e agendamento

Revision ID: 008
Revises: 007
Create Date: 2026-05-12 00:00:00.000000

Mudancas:
- Cria enum stability_level (unstable, stable, very_stable)
- Adiciona em monitored_products:
    stability_level                      stability_level  NOT NULL  default 'unstable'
    last_price_changed_at                TIMESTAMPTZ      NULL
    last_significant_price_change_percent NUMERIC(8,4)    NULL
    last_availability_changed_at         TIMESTAMPTZ      NULL
    last_scheduled_delay_minutes         INTEGER          NULL
    collection_lease_until               TIMESTAMPTZ      NULL
    last_collection_started_at           TIMESTAMPTZ      NULL
    last_collection_finished_at          TIMESTAMPTZ      NULL
    consecutive_failures                 INTEGER          NOT NULL  default 0
    next_check_reason                    VARCHAR(64)      NULL
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE stability_level AS ENUM ('unstable', 'stable', 'very_stable')")

    op.add_column(
        "monitored_products",
        sa.Column(
            "stability_level",
            sa.Enum("unstable", "stable", "very_stable", name="stability_level", create_type=False),
            nullable=False,
            server_default="unstable",
        ),
    )
    op.add_column(
        "monitored_products",
        sa.Column("last_price_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "monitored_products",
        sa.Column("last_significant_price_change_percent", sa.Numeric(8, 4), nullable=True),
    )
    op.add_column(
        "monitored_products",
        sa.Column("last_availability_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "monitored_products",
        sa.Column("last_scheduled_delay_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "monitored_products",
        sa.Column("collection_lease_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "monitored_products",
        sa.Column("last_collection_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "monitored_products",
        sa.Column("last_collection_finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "monitored_products",
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "monitored_products",
        sa.Column("next_check_reason", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("monitored_products", "next_check_reason")
    op.drop_column("monitored_products", "consecutive_failures")
    op.drop_column("monitored_products", "last_collection_finished_at")
    op.drop_column("monitored_products", "last_collection_started_at")
    op.drop_column("monitored_products", "collection_lease_until")
    op.drop_column("monitored_products", "last_scheduled_delay_minutes")
    op.drop_column("monitored_products", "last_availability_changed_at")
    op.drop_column("monitored_products", "last_significant_price_change_percent")
    op.drop_column("monitored_products", "last_price_changed_at")
    op.drop_column("monitored_products", "stability_level")

    op.execute("DROP TYPE stability_level")
