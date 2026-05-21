/* global React, Icon, VariationBadge, StatusDot, ComparisonBadge, MarketplaceChip, Sparkline, brl, applyMonitorFilter */
// Tabela de produtos: projecao compacta do modelo de tela gerado pelos mappers.

function MonitorTable({ products, onOpen, filter, hideHead = false }) {
  const filtered = applyMonitorFilter(products, filter);
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
          // Cor da tendencia acompanha variacao calculada no enriquecimento com historico.
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
                <div style={{color: p.is_price_stale ? 'var(--ma-fg-muted)' : 'var(--ma-fg-strong)', fontWeight: 600, display:'flex', alignItems:'center', gap: 5}}>
                  {brl(p.current_price)}
                  {p.is_price_stale && <Icon name="warning" size={11} color="var(--ma-danger)" title="Preço obsoleto - última coleta falhou"/>}
                </div>
                {p.previous_price != null && p.previous_price !== p.current_price && !p.is_price_stale && (
                  <span className="sub">era {brl(p.previous_price)}</span>
                )}
                {p.is_price_stale && (
                  <span className="sub" style={{color: 'var(--ma-danger)'}}>obsoleto</span>
                )}
              </td>
              <td style={{textAlign:'right'}}>
                {!p.is_price_stale && <VariationBadge value={p.variation_24h}/>}
              </td>
              <td className="num">
                {cmp && (cmp.valid_competitors_count || 0) > 0 && cmp.run_status !== 'no_competitors' && cmp.run_status !== 'expired'
                  ? <span style={{fontFamily:'var(--ma-font-mono)', fontWeight: 700, color: cmp.ranking === 1 ? 'var(--ma-success)' : 'var(--ma-fg-strong)'}}>
                      #{cmp.ranking} <span style={{color:'var(--ma-fg-subtle)', fontWeight: 400}}>de {cmp.participants_count || '?'}</span>
                    </span>
                  : <span style={{fontSize: 11, color: 'var(--ma-fg-subtle)', fontFamily:'var(--ma-font-mono)'}}>
                      {cmp ? '— / —' : 'sem comparação'}
                    </span>
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

Object.assign(window, { MonitorTable });
