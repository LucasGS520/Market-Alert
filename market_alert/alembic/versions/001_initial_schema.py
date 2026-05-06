"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enums
    product_status = postgresql.ENUM("active", "paused", "error", name="product_status")
    product_status.create(op.get_bind(), checkfirst=True)

    comparison_status = postgresql.ENUM("competitive", "attention", "urgent", name="comparison_status")
    comparison_status.create(op.get_bind(), checkfirst=True)

    notification_event_type = postgresql.ENUM(
        "price_drop", "price_rise", "status_change", name="notification_event_type"
    )
    notification_event_type.create(op.get_bind(), checkfirst=True)

    notification_channel = postgresql.ENUM("ntfy", "telert", name="notification_channel")
    notification_channel.create(op.get_bind(), checkfirst=True)

    # monitored_products
    op.create_table(
        "monitored_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("status", sa.Enum("active", "paused", "error", name="product_status"), server_default="active", nullable=False),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_interval_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("consecutive_unchanged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )

    # competitors
    op.create_table(
        "competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("monitored_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["monitored_id"], ["monitored_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("monitored_id", "url", name="uq_competitor_monitored_url"),
    )

    # price_history
    op.create_table(
        "price_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("monitored_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("competitor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(monitored_id IS NOT NULL)::int + (competitor_id IS NOT NULL)::int = 1",
            name="ck_price_history_single_owner",
        ),
        sa.ForeignKeyConstraint(["monitored_id"], ["monitored_products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_history_monitored_collected", "price_history", ["monitored_id", "collected_at"])
    op.create_index("ix_price_history_competitor_collected", "price_history", ["competitor_id", "collected_at"])

    # comparisons
    op.create_table(
        "comparisons",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("monitored_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum("competitive", "attention", "urgent", name="comparison_status"), nullable=False),
        sa.Column("ranking", sa.Integer(), nullable=False),
        sa.Column("average_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("potential_adjustment", sa.Numeric(12, 2), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["monitored_id"], ["monitored_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comparisons_monitored_calculated", "comparisons", ["monitored_id", "calculated_at"])

    # notification_logs
    op.create_table(
        "notification_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("monitored_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Enum("price_drop", "price_rise", "status_change", name="notification_event_type"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("channel", sa.Enum("ntfy", "telert", name="notification_channel"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["monitored_id"], ["monitored_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("notification_logs")
    op.drop_index("ix_comparisons_monitored_calculated", table_name="comparisons")
    op.drop_table("comparisons")
    op.drop_index("ix_price_history_competitor_collected", table_name="price_history")
    op.drop_index("ix_price_history_monitored_collected", table_name="price_history")
    op.drop_table("price_history")
    op.drop_table("competitors")
    op.drop_table("monitored_products")

    for name in ("notification_channel", "notification_event_type", "comparison_status", "product_status"):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
