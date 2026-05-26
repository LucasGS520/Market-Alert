/* global React, Icon, VariationBadge, Card, MarketplaceChip, brl, Sparkline, EVENT_META */
// Cards do dashboard: agregacoes visuais calculadas a partir dos dados ja carregados.

function KpiCard({ label, value, sub, accent }) {
  return (
    <Card>
      <div className="ma-kpi-label">{label}</div>
      <div className="ma-kpi-value" style={accent ? { color: accent } : null}>{value}</div>
      <div className="ma-kpi-sub">{sub}</div>
    </Card>
  );
}

function TopMoverCard({ product, onOpen }) {
  // variation_all é a tendência acumulada do produto; variation_24h é o detalhe recente.
  const primaryVar = product.variation_all ?? product.variation_24h ?? 0;
  // Cor e dados do sparkline refletem tendência do mercado (average_price), não do monitorado.
  const mks = product.market_avg_sparkline || [];
  const mktColor = mks.length >= 2
    ? (mks[mks.length - 1] > mks[0] ? 'var(--ma-success)' : 'var(--ma-danger)')
    : (primaryVar > 0.1 ? 'var(--ma-danger)' : 'var(--ma-success)');
  return (
    <button
      onClick={() => onOpen(product.id)}
      className="ma-card is-padded"
      style={{textAlign:'left', cursor:'pointer', display:'block', width:'100%', border:'1px solid var(--ma-border)'}}>
      <div style={{display:'flex', alignItems:'center', gap: 10, marginBottom: 12}}>
        <div className="cell-thumb">
          {product.thumbnail_url
            ? <img src={product.thumbnail_url} alt="" width={28} height={28} style={{borderRadius: 4, objectFit: 'cover', display: 'block'}}/>
            : <Icon name={product.icon || 'package'} size={16}/>}
        </div>
        <div style={{flex: 1, minWidth: 0}}>
          <div style={{fontSize: 13, fontWeight: 700, color:'var(--ma-fg-strong)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis'}}>{product.name}</div>
          <div style={{marginTop: 4}}><MarketplaceChip marketplace={product.marketplace} size="sm"/></div>
        </div>
      </div>
      <div style={{display:'flex', alignItems:'flex-end', justifyContent:'space-between', gap: 10}}>
        <div style={{minWidth: 0}}>
          <div style={{fontFamily:'var(--ma-font-display)', fontSize: 22, fontWeight: 800, color: 'var(--ma-fg-strong)', fontVariantNumeric:'tabular-nums', letterSpacing:'-0.02em', whiteSpace:'nowrap'}}>{brl(product.current_price)}</div>
          <div style={{marginTop: 6, display:'flex', alignItems:'center', gap: 6, flexWrap:'wrap'}}>
            <VariationBadge value={product.variation_all ?? product.variation_24h}/>
            {product.variation_all != null && product.variation_24h != null && (
              <span style={{fontSize: 11, color: 'var(--ma-fg-subtle)', fontFamily: 'var(--ma-font-mono)', whiteSpace:'nowrap'}}>
                24h {product.variation_24h > 0 ? '+' : ''}{product.variation_24h.toFixed(1)}%
              </span>
            )}
          </div>
        </div>
        <Sparkline data={mks} width={80} height={32} color={mktColor}/>
      </div>
    </button>
  );
}

function MiniAlertRow({ n, onOpen }) {
  // Linha compacta para alertas recentes; a tela completa fica em screens/alerts.
  const meta = EVENT_META[n.event_type] || { label: n.event_type, icon: 'bell', tone: 'brand' };
  const toneColor = {
    success: 'var(--ma-success)',
    danger:  'var(--ma-danger)',
    warning: 'var(--ma-warning)',
    info:    'var(--ma-info)',
    brand:   'var(--ma-brand-primary)',
  }[meta.tone] || 'var(--ma-fg-muted)';
  return (
    <button
      onClick={() => n.monitored_id && onOpen && onOpen(n.monitored_id)}
      style={{display:'grid', gridTemplateColumns: '24px 1fr auto', gap: 12, padding: '10px 14px', background:'transparent', border:0, borderBottom: '1px solid var(--ma-border)', textAlign:'left', cursor: n.monitored_id ? 'pointer' : 'default', width:'100%', color: 'var(--ma-fg)'}}>
      <div style={{width: 24, height: 24, borderRadius: 6, background: `color-mix(in srgb, ${toneColor} 18%, transparent)`, color: toneColor, display:'flex', alignItems:'center', justifyContent:'center'}}>
        <Icon name={meta.icon} size={13}/>
      </div>
      <div style={{minWidth: 0}}>
        <div style={{fontSize: 12, fontWeight: 600, color: 'var(--ma-fg-strong)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis'}}>{n.title || n.message}</div>
        <div className="ma-meta" style={{marginTop: 1}}>{n.sent_at}</div>
      </div>
      <Icon name="chevron-right" size={14} color="var(--ma-fg-subtle)"/>
    </button>
  );
}

Object.assign(window, { KpiCard, TopMoverCard, MiniAlertRow });
