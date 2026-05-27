"""notification_logs: adiciona collection_health_alert ao enum

Revision ID: 021
Revises: 020
Create Date: 2026-05-27 00:00:00.000000

Contexto:
    Adiciona o tipo collection_health_alert ao enum notification_event_type.
    Este tipo é entregável ao usuário (DELIVERABLE_ALERT_TYPES) e representa
    falhas técnicas de coleta em qualquer entidade do grupo monitorado.
"""

from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TYPE notification_event_type ADD VALUE IF NOT EXISTS 'collection_health_alert'"
    ))


def downgrade() -> None:
    # PostgreSQL não suporta remoção de enum values.
    # Removemos as linhas que usam o tipo e recriamos o enum sem ele.
    conn = op.get_bind()

    conn.execute(sa.text(
        "DELETE FROM notification_logs WHERE event_type = 'collection_health_alert'"
    ))

    conn.execute(sa.text("ALTER TYPE notification_event_type RENAME TO notification_event_type_old"))
    conn.execute(sa.text(
        "CREATE TYPE notification_event_type AS ENUM ("
        "'competitive_threat_alert', 'competitive_opportunity_alert', "
        "'market_movement_alert', 'reference_availability_alert', "
        "'competitor_price_movement_alert', 'competitor_availability_alert', "
        "'notification_suppressed'"
        ")"
    ))
    conn.execute(sa.text(
        "ALTER TABLE notification_logs "
        "ALTER COLUMN event_type TYPE notification_event_type "
        "USING event_type::text::notification_event_type"
    ))
    conn.execute(sa.text("DROP TYPE notification_event_type_old"))
