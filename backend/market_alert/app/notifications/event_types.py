ACTIVE_TYPES: frozenset[str] = frozenset({
    # Hierarquia por impacto competitivo — gerados via _decide_alert() em tasks.py
    "competitive_threat_alert",
    "competitive_opportunity_alert",
    "market_movement_alert",
    "reference_availability_alert",
    # Gerado diretamente pelo collector_task (mudança de disponibilidade do produto)
    "availability_alert",
})

# Gerados pelo pipeline antigo (antes da migração 019).
# Podem existir em notification_logs como histórico, mas nenhum caminho em tasks.py os produz hoje.
DEPRECATED_TYPES: frozenset[str] = frozenset({
    "price_drop_alert",
    "price_rise_alert",
    "competitive_position_alert",
    "market_alert",
    "error_alert",
})

# Nunca entregue ao usuário — usado apenas como marcador de auditoria operacional.
# registrar_supressao() usa este tipo para registrar bloqueios pré-decisão (quorum, run degradado).
AUDIT_ONLY_TYPES: frozenset[str] = frozenset({
    "collection_health_alert",
})

# Definidos no schema DB (migration 019) mas sem lógica de geração implementada ainda.
INACTIVE_TYPES: frozenset[str] = frozenset({
    "competitor_movement_alert",
    "competitor_availability_alert",
})

# Preservados para compatibilidade com linhas históricas — não são gerados pelo pipeline atual.
LEGACY_TYPES: frozenset[str] = frozenset({
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
})

ALL_TYPES: frozenset[str] = ACTIVE_TYPES | DEPRECATED_TYPES | AUDIT_ONLY_TYPES | INACTIVE_TYPES | LEGACY_TYPES

# Subconjunto que pode ser enviado via ntfy. send_notification() rejeita qualquer tipo fora deste set.
DELIVERABLE_TYPES: frozenset[str] = ACTIVE_TYPES
