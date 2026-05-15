/* global React, Icon, Button, VariationBadge, Card, StatusDot, ComparisonBadge, MarketplaceChip, brl, Sparkline, MonitorTable, EVENT_META */

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
  const up = (product.variation_24h || 0) > 0.1;
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
          <div style={{marginTop: 6, display:'flex', alignItems:'center', gap: 6}}>
            <VariationBadge value={product.variation_24h}/>
            {product.latest_comparison && (
              <span style={{fontSize: 11, color: 'var(--ma-fg-subtle)', fontFamily: 'var(--ma-font-mono)'}}>
                #{product.latest_comparison.ranking}/{product.latest_comparison.participants_count || '?'}
              </span>
            )}
          </div>
        </div>
        <Sparkline data={product.history} width={80} height={32}
          color={up ? 'var(--ma-danger)' : 'var(--ma-success)'}/>
      </div>
    </button>
  );
}

function MiniAlertRow({ n, onOpen }) {
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

function Painel({ products, notifications, onOpen, onAdd, onAllAlerts }) {
  const activeProducts  = products.filter(p => p.status === 'active').length;
  const pausedProducts  = products.filter(p => p.status === 'paused').length;
  const errorProducts   = products.filter(p => p.status === 'error' || p.status === 'unsupported').length;
  const urgentCount     = products.filter(p => p.latest_comparison?.status === 'urgent').length;
  const totalCompetitors = products.reduce((acc, p) => acc + (p.competitors_count || 0), 0);
  const todaySent   = notifications.filter(n => n.delivery_status === 'sent').length;
  const todayFailed = notifications.filter(n => n.delivery_status === 'failed').length;
  const todaySkipped = notifications.filter(n => n.delivery_status === 'skipped').length;

  const movers = [...products]
    .filter(p => Math.abs(p.variation_24h || 0) > 0.1)
    .sort((a,b) => Math.abs(b.variation_24h || 0) - Math.abs(a.variation_24h || 0))
    .slice(0, 3);

  const recentAlerts = notifications.filter(n => n.delivery_status === 'sent').slice(0, 4);

  return (
    <div>
      <div className="ma-page-head">
        <div>
          <h1>Painel</h1>
          <div className="sub">{products.length} produto{products.length !== 1 ? 's' : ''} · {totalCompetitors} concorrente{totalCompetitors !== 1 ? 's' : ''} monitorado{totalCompetitors !== 1 ? 's' : ''}</div>
        </div>
        <div className="right">
          <Button kind="primary" leading="plus" onClick={onAdd}>Adicionar produto</Button>
        </div>
      </div>

      <div className="ma-kpi">
        <KpiCard label="Produtos monitorados" value={products.length}
          sub={`${activeProducts} ativo${activeProducts !== 1 ? 's' : ''} · ${pausedProducts} pausado${pausedProducts !== 1 ? 's' : ''} · ${errorProducts} com erro`}/>
        <KpiCard label="Em estado urgente" value={urgentCount}
          sub="comparações fora da posição-alvo"
          accent={urgentCount > 0 ? 'var(--ma-brand-primary)' : undefined}/>
        <KpiCard label="Alertas entregues" value={todaySent}
          sub={`${todayFailed} falharam · ${todaySkipped} ignorados`}/>
        <KpiCard label="Concorrentes cobertos" value={totalCompetitors}
          sub={`em ${activeProducts} produto${activeProducts !== 1 ? 's' : ''} ativo${activeProducts !== 1 ? 's' : ''}`}/>
      </div>

      <div style={{display:'grid', gridTemplateColumns: '1.6fr 1fr', gap: 16, marginTop: 22}}>
        <div>
          <div className="ma-section-head" style={{marginTop: 0}}>
            <h2>Maiores variações</h2>
            <span className="ma-section-meta">últimas 24h</span>
            <div className="right">
              <Button kind="ghost" size="sm" trailing="arrow-right" onClick={() => window.MA_NAV && window.MA_NAV('monitors')}>Ver todos</Button>
            </div>
          </div>
          <div style={{display:'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12}}>
            {movers.map(p => <TopMoverCard key={p.id} product={p} onOpen={onOpen}/>)}
            {movers.length === 0 && (
              <div style={{gridColumn: '1/-1', padding: 24, border: '1px dashed var(--ma-border-strong)', borderRadius: 'var(--ma-radius-md)', color: 'var(--ma-fg-subtle)', fontSize: 12, display:'flex', alignItems:'center', justifyContent:'center', textAlign:'center'}}>
                Sem variações relevantes nas últimas 24h
              </div>
            )}
            {movers.length > 0 && movers.length < 3 && Array.from({length: 3 - movers.length}).map((_, i) => (
              <div key={'ph'+i} style={{padding: 16, border: '1px dashed var(--ma-border-strong)', borderRadius: 'var(--ma-radius-md)', color: 'var(--ma-fg-subtle)', fontSize: 12, display:'flex', alignItems:'center', justifyContent:'center', textAlign:'center'}}>Sem variações relevantes</div>
            ))}
          </div>
        </div>
        <div>
          <div className="ma-section-head" style={{marginTop: 0, flexWrap: 'wrap', rowGap: 4}}>
            <h2>Alertas recentes</h2>
            <div className="right">
              <Button kind="ghost" size="sm" trailing="arrow-right" onClick={onAllAlerts}>Ver todos</Button>
            </div>
          </div>
          {recentAlerts.length > 0 ? (
            <Card padded={false}>
              {recentAlerts.map(n => <MiniAlertRow key={n.id} n={n} onOpen={onOpen}/>)}
            </Card>
          ) : (
            <div style={{padding: '24px 0', textAlign:'center', color:'var(--ma-fg-muted)', fontSize: 12}}>Nenhum alerta entregue ainda.</div>
          )}
        </div>
      </div>

      {products.length > 0 && (
        <>
          <div className="ma-section-head" style={{marginTop: 28}}>
            <h2>Produtos monitorados</h2>
            <span className="ma-section-meta">visão compacta · clique para abrir</span>
            <div className="right">
              <Button kind="ghost" size="sm" trailing="arrow-right" onClick={() => window.MA_NAV && window.MA_NAV('monitors')}>Ir para Monitoramento</Button>
            </div>
          </div>
          <MonitorTable products={products.slice(0, 5)} onOpen={onOpen} filter="all"/>
        </>
      )}

      {products.length === 0 && (
        <div style={{marginTop: 40, textAlign:'center', padding: '60px 20px', border: '1px dashed var(--ma-border-strong)', borderRadius: 'var(--ma-radius-lg)', color: 'var(--ma-fg-muted)'}}>
          <Icon name="package" size={32} color="var(--ma-fg-subtle)"/>
          <div style={{marginTop: 12, fontSize: 16, fontWeight: 700, color: 'var(--ma-fg-strong)'}}>Nenhum produto monitorado</div>
          <div style={{marginTop: 6, fontSize: 13}}>Adicione sua primeira URL para começar a monitorar preços.</div>
          <div style={{marginTop: 20}}>
            <Button kind="primary" leading="plus" onClick={onAdd}>Adicionar produto</Button>
          </div>
        </div>
      )}
    </div>
  );
}

Object.assign(window, { Painel, KpiCard, TopMoverCard });
