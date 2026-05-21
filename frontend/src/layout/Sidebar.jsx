/* global React, Icon */
// Navegacao lateral controlada pelo App; nao possui estado proprio de rota.

function Sidebar({ screen, setScreen, alertsCount, products, nextCollect }) {
  const items = [
    { id: 'dashboard',   label: 'Painel',         icon: 'home' },
    { id: 'monitors',    label: 'Monitoramento',  icon: 'eye',  count: products.length },
    { id: 'alerts',      label: 'Alertas',        icon: 'bell', count: alertsCount || undefined },
  ];
  return (
    <aside className="ma-sidebar">
      <div className="ma-logo">
        <img className="ma-logo-wordmark" src="assets/logo_wordmark_transparente.png" alt="Market Alert" decoding="async"/>
      </div>
      <div className="ma-nav" style={{marginTop: 4}}>
        {items.map(it => (
          <button key={it.id}
            className={`ma-nav-item ${screen === it.id ? 'is-active' : ''}`}
            onClick={() => setScreen(it.id)}>
            <Icon name={it.icon} size={16}/>
            <span>{it.label}</span>
            {it.count != null && it.count > 0 && <span className="ma-nav-count">{it.count}</span>}
          </button>
        ))}
      </div>
      <div style={{flex: 1}}/>
      {nextCollect && (
        <div style={{padding: '12px 10px', borderTop: '1px solid var(--ma-border)', marginTop: 12}}>
          <div className="ma-eyebrow" style={{marginBottom: 6, color: 'var(--ma-fg-subtle)'}}>Próxima coleta automática</div>
          <div style={{fontFamily: 'var(--ma-font-mono)', fontSize: 12, color: 'var(--ma-fg)', display:'flex', alignItems:'center', gap:6}}>
            <span className="ma-statusdot-dot" style={{width:6, height:6, borderRadius:'50%', background:'var(--ma-success-strong)', boxShadow:'0 0 8px var(--ma-success-strong)'}}/>
            {nextCollect}
          </div>
        </div>
      )}
    </aside>
  );
}

Object.assign(window, { Sidebar });
