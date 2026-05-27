// Fonte de verdade para metadados de tipos de notificação.
// Consumido por badges.jsx (EVENT_META), Alerts.jsx (TYPE_GROUPS) e mappers.js (URGENT_TYPES).
// Carregado via script tag antes dos consumidores; expõe globais via window.

const EVENT_META = {
  // ── Tier 1 — alertas primários entregáveis ────────────────────────────────
  competitive_threat_alert:        { label: 'Ameaça competitiva',     icon: 'warning',    tone: 'danger'   },
  competitive_opportunity_alert:   { label: 'Oportunidade',           icon: 'trend-up',   tone: 'success'  },
  market_movement_alert:           { label: 'Movimento de mercado',   icon: 'trend-down', tone: 'info'     },
  reference_availability_alert:    { label: 'Disponibilidade ref.',   icon: 'eye',        tone: 'warning'  },
  // ── Tier 2 — alertas por concorrente entregáveis ─────────────────────────
  competitor_price_movement_alert: { label: 'Variação de preço',      icon: 'zap',        tone: 'info'     },
  competitor_availability_alert:   { label: 'Disponib. concorrente',  icon: 'eye',        tone: 'info'     },
  // ── Auditoria operacional — nunca entregue ao usuário ─────────────────────
  notification_suppressed:         { label: 'Supressão operacional',  icon: 'warning',    tone: 'warning'  },
};

// Grupos usados pelos filtros da tela de Alertas.
const TYPE_GROUPS = {
  competitive:  ['competitive_threat_alert', 'competitive_opportunity_alert'],
  market:       ['market_movement_alert', 'competitor_price_movement_alert'],
  availability: ['reference_availability_alert', 'competitor_availability_alert'],
  collection:   ['notification_suppressed'],
};

// Tipos que recebem classificação visual 'urgent' no mapNotification.
const URGENT_TYPES = new Set([
  'competitive_threat_alert',
  'competitive_opportunity_alert',
]);

Object.assign(window, { EVENT_META, TYPE_GROUPS, URGENT_TYPES });
