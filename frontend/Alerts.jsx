/* global React, Icon, Button, Card, MarketplaceChip, DeliveryPill, EVENT_META, brl */

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

function Alerts({ notifications, products, onOpen }) {
  const [filter, setFilter] = React.useState('all');
  const [deliveryFilter, setDeliveryFilter] = React.useState('all');

  const filterMatches = (n) => {
    if (deliveryFilter !== 'all' && n.delivery_status !== deliveryFilter) return false;
    switch (filter) {
      case 'all':          return true;
      case 'price':        return n.event_type === 'price_drop' || n.event_type === 'price_rise';
      case 'ranking':      return n.event_type === 'ranking_change';
      case 'market':       return n.event_type === 'market_price_drop' || n.event_type === 'market_price_rise';
      case 'availability': return ['product_unavailable','product_available','competitor_unavailable','competitor_available'].includes(n.event_type);
      case 'collection':   return n.event_type === 'status_change';
      default: return true;
    }
  };
  const visible = notifications.filter(filterMatches);

  const filters = [
    { id: 'all',          label: 'Todos',           count: notifications.length },
    { id: 'price',        label: 'Preço',           count: notifications.filter(n => ['price_drop','price_rise'].includes(n.event_type)).length },
    { id: 'ranking',      label: 'Ranking',         count: notifications.filter(n => n.event_type === 'ranking_change').length },
    { id: 'market',       label: 'Mercado',         count: notifications.filter(n => ['market_price_drop','market_price_rise'].includes(n.event_type)).length },
    { id: 'availability', label: 'Disponibilidade', count: notifications.filter(n => ['product_unavailable','product_available','competitor_unavailable','competitor_available'].includes(n.event_type)).length },
    { id: 'collection',   label: 'Coleta',          count: notifications.filter(n => n.event_type === 'status_change').length },
  ];

  const deliveryFilters = [
    { id: 'all',     label: 'Todos' },
    { id: 'sent',    label: 'Enviados' },
    { id: 'failed',  label: 'Falharam' },
    { id: 'skipped', label: 'Ignorados' },
  ];

  return (
    <div>
      <div className="ma-page-head">
        <div>
          <h1>Alertas</h1>
          <div className="sub">Histórico de tentativas de entrega via ntfy</div>
        </div>
      </div>

      <div className="ma-section-head" style={{margin: '4px 0 10px', flexWrap: 'wrap', rowGap: 8}}>
        <div className="ma-chips">
          {filters.map(f => (
            <button key={f.id}
              className={`ma-chip ${filter === f.id ? 'is-active' : ''}`}
              onClick={() => setFilter(f.id)}>
              {f.label} <span style={{opacity: 0.6, fontFamily: 'var(--ma-font-mono)', marginLeft: 4}}>{f.count}</span>
            </button>
          ))}
        </div>
        <div className="ma-chips" style={{marginLeft: 'auto'}}>
          {deliveryFilters.map(f => (
            <button key={f.id}
              className={`ma-chip ${deliveryFilter === f.id ? 'is-active' : ''}`}
              style={{fontSize: 11, padding: '4px 10px'}}
              onClick={() => setDeliveryFilter(f.id)}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <div style={{padding: '60px 0', textAlign:'center', color:'var(--ma-fg-muted)', fontSize: 13}}>
          <Icon name="inbox" size={32} color="var(--ma-fg-subtle)"/>
          <div style={{marginTop: 10}}>Nenhum alerta encontrado para este filtro.</div>
        </div>
      ) : (
        visible.map(n => <AlertCard key={n.id} n={n} products={products} onOpen={onOpen}/>)
      )}
    </div>
  );
}

Object.assign(window, { Alerts });
