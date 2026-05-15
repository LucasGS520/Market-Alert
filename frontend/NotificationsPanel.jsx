/* global React, Icon, IconButton, Button, EVENT_META, DeliveryPill */

function DrawerNotification({ n, onOpen }) {
  const meta = EVENT_META[n.event_type] || { label: n.event_type, icon: 'bell', tone: 'brand' };
  const toneColor = {
    success: 'var(--ma-success)', danger: 'var(--ma-danger)',
    warning: 'var(--ma-warning)', info: 'var(--ma-info)', brand: 'var(--ma-brand-primary)',
  }[meta.tone] || 'var(--ma-fg-muted)';
  return (
    <div
      onClick={() => n.monitored_id && onOpen && onOpen(n.monitored_id)}
      style={{display:'grid', gridTemplateColumns: '32px 1fr auto', gap: 12, padding: '12px 14px', borderRadius: 'var(--ma-radius-md)', border: '1px solid var(--ma-border)', background: 'var(--ma-neutral-500)', marginBottom: 8, cursor: n.monitored_id ? 'pointer' : 'default'}}>
      <div style={{width: 32, height: 32, borderRadius: 8, background: `color-mix(in srgb, ${toneColor} 18%, transparent)`, color: toneColor, display:'flex', alignItems:'center', justifyContent:'center'}}>
        <Icon name={meta.icon} size={15}/>
      </div>
      <div style={{minWidth: 0}}>
        <div style={{display:'flex', gap: 8, alignItems: 'center', marginBottom: 4}}>
          <span style={{fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform:'uppercase', color: toneColor}}>{meta.label}</span>
          <DeliveryPill status={n.delivery_status}/>
        </div>
        <div style={{fontSize: 13, fontWeight: 700, color: 'var(--ma-fg-strong)'}}>{n.title || n.message}</div>
        <div style={{fontSize: 12, color: 'var(--ma-fg)', marginTop: 4, lineHeight: 1.5}}>{n.message}</div>
      </div>
      <div style={{fontFamily:'var(--ma-font-mono)', fontSize: 10, color:'var(--ma-fg-subtle)', whiteSpace: 'nowrap'}}>{n.sent_at}</div>
    </div>
  );
}

function NotificationsPanel({ open, onClose, notifications, onOpenProduct }) {
  if (!open) return null;
  const sent = notifications.filter(n => n.delivery_status === 'sent');
  return (
    <>
      <div className="ma-drawer-mask" onClick={onClose}/>
      <div className="ma-drawer">
        <div className="ma-drawer-head">
          <Icon name="bell" size={16} style={{color: 'var(--ma-brand-primary)', marginRight: 8}}/>
          <h2>Alertas recentes</h2>
          <span className="ma-meta" style={{marginLeft: 10}}>{sent.length} entregue{sent.length !== 1 ? 's' : ''}</span>
          <div style={{marginLeft: 'auto', display:'flex', gap: 6}}>
            <Button kind="ghost" size="sm" onClick={() => { onClose(); window.MA_NAV && window.MA_NAV('alerts'); }}>Ver página completa</Button>
            <IconButton name="x" onClick={onClose} title="Fechar" size="sm"/>
          </div>
        </div>
        <div className="ma-drawer-body">
          {notifications.length === 0 && (
            <div style={{padding: '40px 0', textAlign:'center', color:'var(--ma-fg-muted)', fontSize: 12}}>
              Nenhum alerta ainda.
            </div>
          )}
          {notifications.slice(0, 8).map(n => <DrawerNotification key={n.id} n={n} onOpen={onOpenProduct}/>)}
        </div>
      </div>
    </>
  );
}

Object.assign(window, { NotificationsPanel });
