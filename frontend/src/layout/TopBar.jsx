/* global React, Icon, IconButton */
// Barra superior recebe callbacks do App para abrir overlays e manter a UI desacoplada.

function TopBar({ openNotifications, alertsCount }) {
  return (
    <header className="ma-topbar">
      <div className="ma-search">
        <Icon name="search" size={14}/>
        <span>Buscar produto, concorrente ou URL...</span>
        <span style={{marginLeft: 'auto', fontFamily: 'var(--ma-font-mono)', fontSize: 10, color: 'var(--ma-fg-subtle)', border: '1px solid var(--ma-border)', padding: '1px 6px', borderRadius: 4}}>⌘K</span>
      </div>
      <div className="ma-spacer"/>
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

Object.assign(window, { TopBar });
