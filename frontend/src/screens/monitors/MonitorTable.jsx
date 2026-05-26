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
    <table className="ma-table" style={{tableLayout: 'fixed'}}>
      {!hideHead && (
        <thead>
          <tr>
            <th style={{width: '36%'}}>Produto</th>
            <th style={{width: 120, textAlign:'right'}}>Preço atual</th>
            <th style={{width: 130, textAlign:'right'}}>Média Mercado</th>
            <th style={{width: 148, textAlign:'center'}}>Status</th>
            <th style={{width: 110, textAlign:'center'}}>Posição</th>
            <th style={{width: 112, textAlign:'center'}}>Tendência</th>
            <th style={{width: 40}}></th>
          </tr>
        </thead>
      )}
      <tbody>
        {filtered.map((p) => {
          const cmp = p.latest_comparison;
          const hasMarket = cmp && cmp.reference_available !== false
            && (cmp.valid_competitors_count || 0) > 0
            && cmp.run_status !== 'no_competitors' && cmp.run_status !== 'expired';

          const mks = p.market_avg_sparkline;
          const mktColor = mks.length >= 2
            ? (mks[mks.length - 1] > mks[0] ? 'var(--ma-success)' : mks[mks.length - 1] < mks[0] ? 'var(--ma-danger)' : 'var(--ma-fg-subtle)')
            : 'var(--ma-fg-subtle)';

          const domain = (() => {
            try { return new URL(p.url_normalized).hostname.replace(/^www\./, ''); }
            catch { return p.url_normalized; }
          })();

          return (
            <tr key={p.id} className="ma-row" onClick={() => onOpen(p.id)}>
              {/* Produto */}
              <td>
                <div className="cell-product">
                  <div className="cell-thumb">
                    {p.thumbnail_url
                      ? <img src={p.thumbnail_url} alt=""/>
                      : <Icon name={p.icon || 'package'} size={18}/>}
                  </div>
                  <div style={{minWidth: 0}}>
                    <div className="cell-name">{p.name || 'Produto'}</div>
                    <div style={{display:'flex', alignItems:'center', gap: 6, marginTop: 3}}>
                      <MarketplaceChip marketplace={p.marketplace} size="sm"/>
                      <span className="cell-url">{domain}</span>
                    </div>
                  </div>
                </div>
              </td>

              {/* Preço atual */}
              <td className="num">
                <div style={{color: p.is_price_stale ? 'var(--ma-fg-muted)' : 'var(--ma-fg-strong)', fontWeight: 600, display:'flex', alignItems:'center', justifyContent:'flex-end', gap: 5}}>
                  {brl(p.current_price)}
                  {p.is_price_stale && <Icon name="warning" size={11} color="var(--ma-danger)" title="Preço obsoleto"/>}
                </div>
                {p.previous_price != null && p.previous_price !== p.current_price && !p.is_price_stale && (
                  <span className="sub">era {brl(p.previous_price)}</span>
                )}
                {p.is_price_stale && (
                  <span className="sub" style={{color: 'var(--ma-danger)'}}>obsoleto</span>
                )}
              </td>

              {/* Média Mercado */}
              <td className="num">
                {hasMarket
                  ? <span style={{fontWeight: 600, color: 'var(--ma-fg-strong)'}}>{brl(cmp.average_price)}</span>
                  : <span style={{color: 'var(--ma-fg-subtle)'}}>—</span>
                }
              </td>

              {/* Status */}
              <td style={{textAlign:'center'}}>
                {cmp?.status
                  ? <ComparisonBadge status={cmp.status}/>
                  : <StatusDot status={p.status}/>}
              </td>

              {/* Posição */}
              <td style={{textAlign:'center', fontFamily:'var(--ma-font-mono)', fontVariantNumeric:'tabular-nums'}}>
                {hasMarket && cmp.ranking != null
                  ? <span style={{fontWeight: 700, color: cmp.ranking === 1 ? 'var(--ma-success)' : 'var(--ma-fg-strong)'}}>
                      #{cmp.ranking} <span style={{color:'var(--ma-fg-subtle)', fontWeight: 400}}>de {cmp.participants_count || '?'}</span>
                    </span>
                  : <span style={{color:'var(--ma-fg-subtle)'}}>—</span>
                }
              </td>

              {/* Tendência — sparkline do preço médio de mercado */}
              <td style={{textAlign:'center'}}>
                <Sparkline data={mks} width={96} height={32} color={mktColor}/>
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
