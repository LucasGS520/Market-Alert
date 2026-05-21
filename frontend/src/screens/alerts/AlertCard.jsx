/* global React, Icon, MarketplaceChip, DeliveryPill, EVENT_META */
// Card de alerta: representa uma tentativa de NotificationLog retornada pela API.

function AlertCard({ n, products, onOpen }) {
  const meta = EVENT_META[n.event_type] || { label: n.event_type, icon: 'bell', tone: 'brand' };
  const toneColor = {
    success: 'var(--ma-success)',
    danger:  'var(--ma-danger)',
    warning: 'var(--ma-warning)',
    info:    'var(--ma-info)',
    brand:   'var(--ma-brand-primary)',
  }[meta.tone] || 'var(--ma-fg-muted)';
  const product = products.find(p => p.id === n.monitored_id);
  // Tentativas falhas/ignoradas ficam menos proeminentes, mas continuam auditaveis.
  const dimmed = n.delivery_status === 'skipped' || n.delivery_status === 'failed';

  return (
    <div
      className="ma-alert-card"
      onClick={() => n.monitored_id && onOpen(n.monitored_id)}
      style={{opacity: dimmed ? 0.85 : 1, cursor: n.monitored_id ? 'pointer' : 'default'}}>
      <div className="ma-alert-icon" style={{background: `color-mix(in srgb, ${toneColor} 18%, transparent)`, color: toneColor}}>
        <Icon name={meta.icon} size={16}/>
      </div>
      <div style={{minWidth: 0, flex: 1}}>
        <div style={{display:'flex', alignItems:'center', gap: 8, flexWrap:'wrap'}}>
          <span style={{fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: toneColor}}>{meta.label}</span>
          <DeliveryPill status={n.delivery_status}/>
          {product && <MarketplaceChip marketplace={product.marketplace} size="sm"/>}
        </div>
        <div className="ma-alert-title">{n.title || n.message}</div>
        <div className="ma-alert-body">{n.message}</div>
        <div className="ma-alert-meta">
          {product && (
            <span style={{display:'inline-flex', alignItems:'center', gap: 5}}>
              <Icon name="package" size={11}/>{product.name}
            </span>
          )}
          {n.run_status && (
            <>
              <span style={{opacity: 0.4}}>·</span>
              <span>rodada <b style={{color: 'var(--ma-fg)'}}>{n.run_status}</b>{n.participants_count != null && ` · ${n.participants_count} fontes`}</span>
            </>
          )}
          {n.error_message && (
            <>
              <span style={{opacity: 0.4}}>·</span>
              <span style={{color: 'var(--ma-danger)', fontFamily: 'var(--ma-font-mono)'}}>{n.error_message}</span>
            </>
          )}
        </div>
      </div>
      <div className="ma-alert-time">{n.sent_at}</div>
    </div>
  );
}

Object.assign(window, { AlertCard });
