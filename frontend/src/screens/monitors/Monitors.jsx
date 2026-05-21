/* global React, Button, MonitorTable */
// Tela de monitoramento: filtra localmente a lista ja carregada pelo App.

function applyMonitorFilter(products, filter) {
  // Filtros sao puramente de apresentacao; nao disparam novas chamadas HTTP.
  switch (filter) {
    case 'urgent':    return products.filter(p => p.latest_comparison?.status === 'urgent');
    case 'attention': return products.filter(p => p.latest_comparison?.status === 'attention');
    case 'down':      return products.filter(p => (p.variation_24h || 0) < -0.1);
    case 'up':        return products.filter(p => (p.variation_24h || 0) > 0.1);
    case 'paused':    return products.filter(p => p.status === 'paused');
    case 'error':     return products.filter(p => p.status === 'error' || p.status === 'unsupported');
    default:          return products;
  }
}

function Monitors({ products, onOpen, onAdd }) {
  const [filter, setFilter] = React.useState('all');
  const filters = [
    { id: 'all',       label: 'Todos',    count: products.length },
    { id: 'urgent',    label: 'Urgente',  count: products.filter(p => p.latest_comparison?.status === 'urgent').length },
    { id: 'attention', label: 'Atenção',  count: products.filter(p => p.latest_comparison?.status === 'attention').length },
    { id: 'down',      label: 'Queda',    count: products.filter(p => (p.variation_24h || 0) < -0.1).length },
    { id: 'up',        label: 'Alta',     count: products.filter(p => (p.variation_24h || 0) > 0.1).length },
    { id: 'paused',    label: 'Pausados', count: products.filter(p => p.status === 'paused').length },
    { id: 'error',     label: 'Com erro', count: products.filter(p => p.status === 'error' || p.status === 'unsupported').length },
  ];
  const filtered = applyMonitorFilter(products, filter);

  return (
    <div>
      <div className="ma-page-head">
        <div>
          <h1>Monitoramento</h1>
          <div className="sub">{products.length} produto{products.length !== 1 ? 's' : ''} cadastrado{products.length !== 1 ? 's' : ''}</div>
        </div>
        <div className="right">
          <Button kind="primary" leading="plus" onClick={onAdd}>Adicionar produto</Button>
        </div>
      </div>

      <div className="ma-section-head" style={{margin: '4px 0 14px'}}>
        <div className="ma-chips">
          {filters.map(f => (
            <button key={f.id}
              className={`ma-chip ${filter === f.id ? (f.id === 'urgent' ? 'is-active is-brand' : 'is-active') : ''}`}
              onClick={() => setFilter(f.id)}>
              {f.label} <span style={{opacity: 0.6, fontFamily: 'var(--ma-font-mono)', marginLeft: 4}}>{f.count}</span>
            </button>
          ))}
        </div>
        <span className="ma-section-meta" style={{marginLeft:'auto'}}>{filtered.length} de {products.length}</span>
      </div>

      <MonitorTable products={products} onOpen={onOpen} filter={filter}/>
    </div>
  );
}

Object.assign(window, { Monitors, applyMonitorFilter });
