"""notification_logs: limpa enum, renomeia tipos e consolida índice único

Revision ID: 020
Revises: 019
Create Date: 2026-05-27 00:00:00.000000

Contexto:
    Remove tipos legados/deprecated do enum notification_event_type.
    Renomeia:
        competitor_movement_alert → competitor_price_movement_alert
        collection_health_alert   → notification_suppressed
    Consolida o índice único de deduplicação:
        o índice antigo (da migration 010) cobria só (comparison_id, event_type).
        Com uma notificação por comparação por produto, esse contrato é preservado
        e o índice volta à forma simples.
"""

from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None

# Tipos que existem no enum atual mas serão removidos
_TYPES_TO_REMOVE = (
    "availability_alert",
    "price_drop_alert",
    "price_rise_alert",
    "competitive_position_alert",
    "market_alert",
    "error_alert",
    "price_drop",
    "price_rise",
    "status_change",
    "ranking_change",
    "product_unavailable",
    "product_available",
    "market_price_drop",
    "market_price_rise",
    "competitor_unavailable",
    "competitor_available",
)

# Tipos finais do enum após a migration
_FINAL_TYPES = (
    "competitive_threat_alert",
    "competitive_opportunity_alert",
    "market_movement_alert",
    "reference_availability_alert",
    "competitor_price_movement_alert",
    "competitor_availability_alert",
    "notification_suppressed",
)


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Remover linhas com tipos que não existirão mais no enum
    placeholders = ", ".join(f"'{t}'" for t in _TYPES_TO_REMOVE)
    conn.execute(
        sa.text(f"DELETE FROM notification_logs WHERE event_type::text IN ({placeholders})")
    )

    # 2. Renomear valores ainda presentes no enum (requer PG14+)
    conn.execute(sa.text(
        "ALTER TYPE notification_event_type RENAME VALUE 'competitor_movement_alert' "
        "TO 'competitor_price_movement_alert'"
    ))
    conn.execute(sa.text(
        "ALTER TYPE notification_event_type RENAME VALUE 'collection_health_alert' "
        "TO 'notification_suppressed'"
    ))

    # 3. Recriar o enum sem os tipos removidos
    #    PostgreSQL não permite DROP de enum values — cria novo tipo, troca coluna, dropa antigo.
    conn.execute(sa.text("ALTER TYPE notification_event_type RENAME TO notification_event_type_old"))
    final_values = ", ".join(f"'{t}'" for t in _FINAL_TYPES)
    conn.execute(sa.text(
        f"CREATE TYPE notification_event_type AS ENUM ({final_values})"
    ))
    conn.execute(sa.text(
        "ALTER TABLE notification_logs "
        "ALTER COLUMN event_type TYPE notification_event_type "
        "USING event_type::text::notification_event_type"
    ))
    conn.execute(sa.text("DROP TYPE notification_event_type_old"))

    # 4. Consolidar índice único — um evento por comparação
    op.drop_index("uq_notification_comparison_event", table_name="notification_logs", if_exists=True)

    op.create_index(
        "uq_notification_comparison_event",
        "notification_logs",
        ["comparison_id", "event_type"],
        unique=True,
        postgresql_where=sa.text("comparison_id IS NOT NULL AND delivery_status = 'sent'"),
    )


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_index("uq_notification_comparison_event", table_name="notification_logs", if_exists=True)

    # Restaurar enum antigo
    conn.execute(sa.text("ALTER TYPE notification_event_type RENAME TO notification_event_type_new"))
    old_values = (
        "competitive_threat_alert", "competitive_opportunity_alert",
        "market_movement_alert", "reference_availability_alert",
        "availability_alert", "collection_health_alert",
        "competitor_movement_alert", "competitor_availability_alert",
        "price_drop_alert", "price_rise_alert", "competitive_position_alert",
        "market_alert", "error_alert",
        "price_drop", "price_rise", "status_change", "ranking_change",
        "product_unavailable", "product_available",
        "market_price_drop", "market_price_rise",
        "competitor_unavailable", "competitor_available",
    )
    old_values_sql = ", ".join(f"'{t}'" for t in old_values)
    conn.execute(sa.text(f"CREATE TYPE notification_event_type AS ENUM ({old_values_sql})"))
    conn.execute(sa.text(
        "ALTER TABLE notification_logs "
        "ALTER COLUMN event_type TYPE notification_event_type "
        "USING event_type::text::notification_event_type"
    ))
    conn.execute(sa.text("DROP TYPE notification_event_type_new"))

    # Restaurar índice único antigo
    op.create_index(
        "uq_notification_comparison_event",
        "notification_logs",
        ["comparison_id", "event_type"],
        unique=True,
        postgresql_where=sa.text("comparison_id IS NOT NULL AND delivery_status = 'sent'"),
    )
