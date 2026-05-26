// Fonte de verdade para metadados de tipos de notificação.
// Consumido por badges.jsx (EVENT_META), Alerts.jsx (TYPE_GROUPS) e mappers.js (URGENT_TYPES).
// Carregado via script tag antes dos consumidores; expõe globais via window.

const EVENT_META = {
  // ── Tipos ativos — gerados pelo pipeline atual ─────────────────────────────
  competitive_threat_alert:      { label: 'Ameaça competitiva',    icon: 'warning',    tone: 'danger'   },
  competitive_opportunity_alert: { label: 'Oportunidade',          icon: 'trend-up',   tone: 'success'  },
  market_movement_alert:         { label: 'Movimento de mercado',  icon: 'trend-down', tone: 'info'     },
  reference_availability_alert:  { label: 'Disponibilidade ref.',  icon: 'eye',        tone: 'warning'  },
  availability_alert:            { label: 'Disponibilidade',       icon: 'eye',        tone: 'warning'  },

  // ── Auditoria operacional — nunca entregue ao usuário ──────────────────────
  collection_health_alert:       { label: 'Saúde de coleta',       icon: 'warning',    tone: 'warning'  },

  // ── Inativos — definidos no schema, sem lógica de geração ainda ────────────
  competitor_movement_alert:     { label: 'Movimento concorrente', icon: 'zap',        tone: 'info'     },
  competitor_availability_alert: { label: 'Concorrente',           icon: 'eye',        tone: 'info'     },

  // ── Deprecated — pipeline antigo; mantidos para exibir registros históricos ─
  price_drop_alert:           { label: 'Queda de preço',      icon: 'arrow-down', tone: 'danger'  },
  price_rise_alert:           { label: 'Alta de preço',       icon: 'arrow-up',   tone: 'success' },
  competitive_position_alert: { label: 'Posição competitiva', icon: 'target',     tone: 'brand'   },
  market_alert:               { label: 'Variação de mercado', icon: 'trend-down', tone: 'info'    },
  error_alert:                { label: 'Problema de coleta',  icon: 'warning',    tone: 'warning' },
};

// Grupos usados pelos filtros da tela de Alertas.
// Contém apenas tipos que o pipeline atual gera — deprecated não aparecem como filtro.
const TYPE_GROUPS = {
  competitive:  ['competitive_threat_alert', 'competitive_opportunity_alert'],
  market:       ['market_movement_alert', 'competitor_movement_alert'],
  availability: ['availability_alert', 'reference_availability_alert', 'competitor_availability_alert'],
  collection:   ['collection_health_alert'],
};

// Tipos que recebem classificação visual 'urgent' no mapNotification.
const URGENT_TYPES = new Set([
  'competitive_threat_alert',
  'competitive_opportunity_alert',
]);

Object.assign(window, { EVENT_META, TYPE_GROUPS, URGENT_TYPES });
