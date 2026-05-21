/* global React, Icon, Button, Card, MonitorTable, KpiCard, TopMoverCard, MiniAlertRow */
// Tela principal: consolida produtos, concorrentes e notificacoes em uma visao operacional.

function Painel({ products, notifications, onOpen, onAdd, onAllAlerts }) {
  // KPIs sao derivados em memoria para manter a API fina e a tela responsiva.
  const activeProducts  = products.filter(p => p.status === 'active').length;
  const pausedProducts  = products.filter(p => p.status === 'paused').length;
  const errorProducts   = products.filter(p => p.status === 'error' || p.status === 'unsupported').length;
  const urgentCount     = products.filter(p => p.latest_comparison?.status === 'urgent').length;
  const totalCompetitors = products.reduce((acc, p) => acc + (p.competitors_count || 0), 0);
  const todaySent   = notifications.filter(n => n.delivery_status === 'sent').length;
  const todayFailed = notifications.filter(n => n.delivery_status === 'failed').length;
  const todaySkipped = notifications.filter(n => n.delivery_status === 'skipped').length;

  const movers = [...products]
    // Variações pequenas sao ignoradas para evitar ruido visual.
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

Object.assign(window, { Painel });
