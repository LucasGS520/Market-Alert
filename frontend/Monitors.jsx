/* global React, Icon, Button, VariationBadge, StatusDot, ComparisonBadge, MarketplaceChip, brl */

function Sparkline({ data, color = '#FF7A1A', width = 90, height = 24 }) {
  if (!data || data.length < 2) {
    return <span style={{display:'inline-block', width, height, background:'var(--ma-neutral-500)', borderRadius: 4, opacity: 0.4}}/>;
  }
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const step = width / (data.length - 1);
  const pts = data.map((v, i) => [i * step, height - 2 - ((v - min) / range) * (height - 4)]);
  const d = 'M ' + pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' L ');
  const last = pts[pts.length-1];
  return (
    <svg className="ma-spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx={last[0]} cy={last[1]} r="2" fill={color}/>
    </svg>
  );
}

function MonitorTable({ products, onOpen, filter, hideHead = false }) {
  const filtered = applyFilter(products, filter);
  if (filtered.length === 0) {
    return (
      <div style={{padding: '40px 0', textAlign: 'center', color: 'var(--ma-fg-muted)', fontSize: 13}}>
        Nenhum produto encontrado para este filtro.
      </div>
    );
  }
  return (
    <table className="ma-table">
      {!hideHead && (
        <thead>
          <tr>
            <th style={{width: '36%'}}>Produto</th>
            <th>Status</th>
            <th>Tend. 7d</th>
            <th style={{textAlign:'right'}}>Preço atual</th>
            <th style={{textAlign:'right'}}>Variação 24h</th>
            <th style={{textAlign:'right'}}>Posição</th>
            <th style={{width: 40}}></th>
          </tr>
        </thead>
      )}
      <tbody>
        {filtered.map((p) => {
          const cmp = p.latest_comparison;
          const varColor = p.variation_24h > 0.1 ? 'var(--ma-danger)' : p.variation_24h < -0.1 ? 'var(--ma-success)' : 'var(--ma-fg-subtle)';
          return (
            <tr key={p.id} className="ma-row" onClick={() => onOpen(p.id)}>
              <td>
                <div className="cell-product">
                  <div className="cell-thumb">
                    {p.thumbnail_url
                      ? <img src={p.thumbnail_url} alt="" width={28} height={28} style={{borderRadius: 4, objectFit: 'cover', display: 'block'}}/>
                      : <Icon name={p.icon || 'package'} size={18}/>}
                  </div>
                  <div style={{minWidth: 0}}>
                    <div className="cell-name">{p.name || 'Produto'}</div>
                    <div style={{display:'flex', alignItems:'center', gap: 8, marginTop: 4}}>
                      <MarketplaceChip marketplace={p.marketplace} size="sm"/>
                      <span style={{fontSize: 11, fontFamily: 'var(--ma-font-mono)', color:'var(--ma-fg-subtle)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', maxWidth: 240}}>{p.url_normalized}</span>
                    </div>
                  </div>
                </div>
              </td>
              <td>
                {cmp?.status
                  ? <ComparisonBadge status={cmp.status}/>
                  : <StatusDot status={p.status}/>}
              </td>
              <td>
                <Sparkline data={p.history} color={varColor}/>
              </td>
              <td className="num">
                <div style={{color: 'var(--ma-fg-strong)', fontWeight: 600}}>{brl(p.current_price)}</div>
                {p.previous_price != null && p.previous_price !== p.current_price && (
                  <span className="sub">era {brl(p.previous_price)}</span>
                )}
              </td>
              <td style={{textAlign:'right'}}>
                <VariationBadge value={p.variation_24h}/>
              </td>
              <td className="num">
                {cmp
                  ? <span style={{fontFamily:'var(--ma-font-mono)', fontWeight: 700, color: cmp.ranking === 1 ? 'var(--ma-success)' : 'var(--ma-fg-strong)'}}>
                      #{cmp.ranking} <span style={{color:'var(--ma-fg-subtle)', fontWeight: 400}}>de {cmp.participants_count || '?'}</span>
                    </span>
                  : <span style={{fontSize: 11, color: 'var(--ma-fg-subtle)', fontFamily:'var(--ma-font-mono)'}}>sem comparação</span>
                }
              </td>
              <td><Icon name="chevron-right" size={14} color="var(--ma-fg-subtle)"/></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function applyFilter(products, filter) {
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
  const filtered = applyFilter(products, filter);

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

Object.assign(window, { Monitors, MonitorTable, Sparkline });
