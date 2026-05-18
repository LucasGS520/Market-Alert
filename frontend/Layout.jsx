/* global React, Icon, IconButton */

function Sidebar({ screen, setScreen, alertsCount, products, nextCollect }) {
  const items = [
    { id: 'dashboard',   label: 'Painel',         icon: 'home' },
    { id: 'monitors',    label: 'Monitoramento',  icon: 'eye',  count: products.length },
    { id: 'alerts',      label: 'Alertas',        icon: 'bell', count: alertsCount || undefined },
  ];
  return (
    <aside className="ma-sidebar">
      <div className="ma-logo">
        <img src="assets/logo-wordmark.svg" alt="Market Alert"/>
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

function TopBar({ openNotifications, openAddProduct, alertsCount }) {
  return (
    <header className="ma-topbar">
      <div className="ma-search">
        <Icon name="search" size={14}/>
        <span>Buscar produto, concorrente ou URL…</span>
        <span style={{marginLeft: 'auto', fontFamily: 'var(--ma-font-mono)', fontSize: 10, color: 'var(--ma-fg-subtle)', border: '1px solid var(--ma-border)', padding: '1px 6px', borderRadius: 4}}>⌘K</span>
      </div>
      <div className="ma-spacer"/>
      <button className="ma-btn ma-btn-primary ma-btn-sm" onClick={openAddProduct}>
        <Icon name="plus" size={12}/><span>Adicionar produto</span>
      </button>
      <div style={{position:'relative'}}>
        <IconButton name="bell" onClick={openNotifications} title="Alertas"/>
        {alertsCount > 0 && (
          <span style={{position:'absolute', top: -2, right: -2, minWidth: 16, height: 16, padding: '0 4px', borderRadius: 999, background: 'var(--ma-brand-primary)', color: '#13141B', fontSize: 10, fontWeight: 700, display:'flex', alignItems:'center', justifyContent:'center'}}>{alertsCount}</span>
        )}
      </div>
      <div className="ma-avatar">MA</div>
    </header>
  );
}

Object.assign(window, { Sidebar, TopBar });
