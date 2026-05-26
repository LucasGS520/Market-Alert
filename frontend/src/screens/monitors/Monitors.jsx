/* global React, Button, MonitorTable */
// Tela de monitoramento: filtra e ordena localmente a lista ja carregada pelo App.

function applyMonitorFilter(products, filter) {
  switch (filter) {
    case 'urgent':    return products.filter(p => p.latest_comparison?.status === 'urgent');
    case 'attention':   return products.filter(p => p.latest_comparison?.status === 'attention');
    case 'competitive': return products.filter(p => p.latest_comparison?.status === 'competitive');
    case 'paused':      return products.filter(p => p.status === 'paused');
    case 'error':     return products.filter(p => p.status === 'error' || p.status === 'unsupported');
    default:          return products;
  }
}

function applyMonitorSort(products, sort) {
  const list = [...products];
  switch (sort) {
    case 'price_asc':  return list.sort((a, b) => (a.current_price || 0) - (b.current_price || 0));
    case 'price_desc': return list.sort((a, b) => (b.current_price || 0) - (a.current_price || 0));
    case 'name_asc':   return list.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'pt-BR'));
    case 'variation':  return list.sort((a, b) => Math.abs(b.variation_24h || 0) - Math.abs(a.variation_24h || 0));
    case 'ranking':    return list.sort((a, b) => (a.latest_comparison?.ranking ?? 999) - (b.latest_comparison?.ranking ?? 999));
    default:           return list.sort((a, b) => (b.last_history_ts || 0) - (a.last_history_ts || 0));
  }
}

function Monitors({ products, onOpen, onAdd }) {
  const [filter, setFilter] = React.useState('all');
  const [sort, setSort] = React.useState('recent');

  const filters = [
    { id: 'all',         label: 'Todos',       count: products.length },
    { id: 'urgent',      label: 'Urgente',     count: products.filter(p => p.latest_comparison?.status === 'urgent').length },
    { id: 'attention',   label: 'Atenção',     count: products.filter(p => p.latest_comparison?.status === 'attention').length },
    { id: 'competitive', label: 'Competitivo', count: products.filter(p => p.latest_comparison?.status === 'competitive').length },
    { id: 'paused',      label: 'Pausados',    count: products.filter(p => p.status === 'paused').length },
    { id: 'error',       label: 'Com erro',    count: products.filter(p => p.status === 'error' || p.status === 'unsupported').length },
  ];

  const filtered    = applyMonitorFilter(products, filter);
  const displayList = applyMonitorSort(filtered, sort);

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

      <div style={{display:'flex', alignItems:'center', gap:12, margin:'4px 0 14px', flexWrap:'wrap'}}>
        <div className="ma-filter-bar">
          {filters.map(f => (
            <button key={f.id}
              className={`ma-filter-item${filter === f.id ? (f.id === 'urgent' ? ' is-active is-brand' : ' is-active') : ''}`}
              onClick={() => setFilter(f.id)}>
              {f.label}
              <span style={{opacity:0.6, fontFamily:'var(--ma-font-mono)', marginLeft:4}}>{f.count}</span>
            </button>
          ))}
        </div>

        <div style={{marginLeft:'auto', display:'flex', alignItems:'center', gap:10}}>
          <span className="ma-section-meta">{filtered.length} de {products.length}</span>
          <select className="ma-sort-select" value={sort} onChange={e => setSort(e.target.value)}>
            <option value="recent">Coleta recente</option>
            <option value="price_asc">Preço: menor → maior</option>
            <option value="price_desc">Preço: maior → menor</option>
            <option value="name_asc">Nome: A → Z</option>
            <option value="variation">Maior variação</option>
            <option value="ranking">Melhor posição</option>
          </select>
        </div>
      </div>

      <MonitorTable products={displayList} onOpen={onOpen} filter="all"/>
    </div>
  );
}

Object.assign(window, { Monitors, applyMonitorFilter });
