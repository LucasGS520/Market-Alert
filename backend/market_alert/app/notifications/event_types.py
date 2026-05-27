DELIVERABLE_ALERT_TYPES: frozenset[str] = frozenset({
    # competitive_* — posição do produto monitorado no mercado (gerados via decide_alert())
    "competitive_threat_alert",
    "competitive_opportunity_alert",
    # market_* — movimento geral do mercado
    "market_movement_alert",
    # reference_* — disponibilidade da oferta monitorada
    "reference_availability_alert",
    # competitor_* — movimento específico de concorrente (gerados via build_competitor_signals())
    "competitor_price_movement_alert",
    "competitor_availability_alert",
    # collection_* — falha técnica de coleta para qualquer entidade do grupo monitorado
    "collection_health_alert",
})

AUDIT_EVENT_TYPES: frozenset[str] = frozenset({
    # Nunca entregue ao usuário — registra supressões operacionais (quorum, rodada degradada)
    "notification_suppressed",
})

ALL_NOTIFICATION_EVENT_TYPES: frozenset[str] = DELIVERABLE_ALERT_TYPES | AUDIT_EVENT_TYPES
