// Fonte de verdade para metadados de tipos de notificação.
// Consumido por badges.jsx (EVENT_META), Alerts.jsx (TYPE_GROUPS) e mappers.js (URGENT_TYPES).
// Carregado via script tag antes dos consumidores; expõe globais via window.

const EVENT_META = {
  // ── Alertas de mercado e posição competitiva ──────────────────────────────
  competitive_threat_alert:        { label: 'Ameaça competitiva',     icon: 'warning',    tone: 'danger'   },
  competitive_opportunity_alert:   { label: 'Oportunidade',           icon: 'trend-up',   tone: 'success'  },
  market_movement_alert:           { label: 'Movimento de mercado',   icon: 'trend-down', tone: 'info'     },
  reference_availability_alert:    { label: 'Disponibilidade ref.',   icon: 'eye',        tone: 'warning'  },
  competitor_price_movement_alert: { label: 'Variação de preço',      icon: 'zap',        tone: 'info'     },
  competitor_availability_alert:   { label: 'Disponib. concorrente',  icon: 'eye',        tone: 'info'     },
  // ── Alertas de coleta ─────────────────────────────────────────────────────
  collection_health_alert:         { label: 'Coleta falhou',          icon: 'alert',      tone: 'warning'  },
};

// Grupos usados pelos filtros da tela de Alertas.
const TYPE_GROUPS = {
  competitive:  ['competitive_threat_alert', 'competitive_opportunity_alert'],
  market:       ['market_movement_alert', 'competitor_price_movement_alert'],
  availability: ['reference_availability_alert', 'competitor_availability_alert'],
  collection:   ['collection_health_alert'],
};

// Tipos que recebem classificação visual 'urgent' no mapNotification.
const URGENT_TYPES = new Set([
  'competitive_threat_alert',
  'competitive_opportunity_alert',
]);

Object.assign(window, { EVENT_META, TYPE_GROUPS, URGENT_TYPES });
