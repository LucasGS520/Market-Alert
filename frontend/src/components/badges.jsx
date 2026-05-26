/* global React, Icon */
// Badges traduzem estados e eventos da API para uma representacao visual estavel.

function VariationBadge({ value, style = 'soft' }) {
  if (value == null) return <span className="ma-var ma-var-soft ma-var-flat">—</span>;
  const sign = value > 0 ? '+' : (value < 0 ? '−' : '');
  const abs = Math.abs(value).toFixed(1).replace('.', ',');
  let cls = 'flat';
  let arrow = null;
  if (value > 0.05) { cls = 'up'; arrow = '▲'; }
  else if (value < -0.05) { cls = 'down'; arrow = '▼'; }
  return (
    <span className={`ma-var ma-var-${cls} ma-var-${style}`}>
      {arrow && <span className="ma-var-arrow">{arrow}</span>}
      {sign}{abs}%
    </span>
  );
}

function StatusDot({ status, label }) {
  const map = {
    pending:     { color: 'var(--ma-info)',           label: 'Pendente',      glow: false },
    active:      { color: 'var(--ma-success-strong)', label: 'Coletando',     glow: true  },
    unavailable: { color: 'var(--ma-warning)',        label: 'Indisponível',  glow: false },
    error:       { color: 'var(--ma-danger)',         label: 'Erro',          glow: false },
    paused:      { color: 'var(--ma-fg-subtle)',      label: 'Pausado',       glow: false },
    unsupported: { color: 'var(--ma-fg-subtle)',      label: 'Não suportado', glow: false },
  }[status] || { color: 'var(--ma-fg-subtle)', label: status || '' };
  return (
    <span className="ma-statusdot">
      <span className="ma-statusdot-dot" style={{ background: map.color, boxShadow: map.glow ? `0 0 8px ${map.color}` : 'none' }}/>
      <span>{label || map.label}</span>
    </span>
  );
}

function ComparisonBadge({ status }) {
  const map = {
    competitive: { label: 'Competitivo', cls: 'comp-competitive', icon: 'check' },
    attention:   { label: 'Atenção',     cls: 'comp-attention',   icon: 'eye'   },
    urgent:      { label: 'Urgente',     cls: 'comp-urgent',      icon: 'bell'  },
  }[status];
  if (!map) return null;
  return (
    <span className={`ma-cmp-badge ${map.cls}`}>
      <Icon name={map.icon} size={11}/>
      {map.label}
    </span>
  );
}

const MARKETPLACE_META = {
  // Mercado Livre e o unico marketplace oficialmente suportado nesta etapa.
  mercadolivre: { label: 'Mercado Livre', short: 'ML', color: '#FFE600', textOnColor: '#13141B' },
};

function MarketplaceChip({ marketplace, size = 'md' }) {
  const m = MARKETPLACE_META[marketplace] || { label: marketplace || 'Outro', short: '·', color: 'var(--ma-neutral-400)', textOnColor: 'var(--ma-fg-strong)' };
  const isSm = size === 'sm';
  return (
    <span className="ma-mp-chip" style={{ fontSize: isSm ? 10 : 11, padding: isSm ? '1px 6px 1px 4px' : '2px 8px 2px 5px' }}>
      <span className="ma-mp-chip-dot" style={{ background: m.color, color: m.textOnColor, fontSize: isSm ? 8 : 9 }}>{m.short}</span>
      {m.label}
    </span>
  );
}

// EVENT_META definido em src/constants/notificationTypes.js (carregado antes via script tag).

const DELIVERY_META = {
  // Metadados visuais para delivery_status da tentativa de notificacao.
  sent:    { label: 'Enviado',     tone: 'success' },
  failed:  { label: 'Falhou',      tone: 'danger'  },
  skipped: { label: 'Ignorado',    tone: 'muted'   },
  pending: { label: 'Enfileirado', tone: 'info'    },
};

function DeliveryPill({ status }) {
  const m = DELIVERY_META[status] || { label: status, tone: 'muted' };
  return <span className={`ma-delivery ma-delivery-${m.tone}`}>{m.label}</span>;
}

function Tag({ tone = 'neutral', children }) {
  return <span className={`ma-tag ma-tag-${tone}`}>{children}</span>;
}

Object.assign(window, {
  VariationBadge, StatusDot, ComparisonBadge, MarketplaceChip, MARKETPLACE_META,
  EVENT_META, DeliveryPill, DELIVERY_META, Tag,
});
