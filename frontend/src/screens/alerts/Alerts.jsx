/* global React, Icon, AlertCard */
// Historico de notificacoes com filtros locais por tipo de evento e status de entrega.

function Alerts({ notifications, products, onOpen }) {
  const [filter, setFilter] = React.useState('all');
  const [deliveryFilter, setDeliveryFilter] = React.useState('all');

  const filterMatches = (n) => {
    // Filtros nao alteram a consulta: operam sobre o lote carregado pelo dashboard.
    if (deliveryFilter !== 'all' && n.delivery_status !== deliveryFilter) return false;
    switch (filter) {
      case 'all':          return true;
      case 'price':        return n.event_type === 'price_drop_alert' || n.event_type === 'price_rise_alert';
      case 'competitive':  return n.event_type === 'competitive_position_alert';
      case 'market':       return n.event_type === 'market_alert';
      case 'availability': return n.event_type === 'availability_alert';
      case 'collection':   return n.event_type === 'error_alert';
      default: return true;
    }
  };
  const visible = notifications.filter(filterMatches);

  const filters = [
    { id: 'all',          label: 'Todos',           count: notifications.length },
    { id: 'price',        label: 'Preço',           count: notifications.filter(n => ['price_drop_alert','price_rise_alert'].includes(n.event_type)).length },
    { id: 'competitive',  label: 'Competitivo',     count: notifications.filter(n => n.event_type === 'competitive_position_alert').length },
    { id: 'market',       label: 'Mercado',         count: notifications.filter(n => n.event_type === 'market_alert').length },
    { id: 'availability', label: 'Disponibilidade', count: notifications.filter(n => n.event_type === 'availability_alert').length },
    { id: 'collection',   label: 'Coleta',          count: notifications.filter(n => n.event_type === 'error_alert').length },
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
