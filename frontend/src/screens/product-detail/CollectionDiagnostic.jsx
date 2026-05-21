/* global React, Icon */
// Diagnostico operacional de coleta. Le o endpoint health sob demanda ao abrir.
const OUTCOME_STYLE = {
  // Traducao visual de outcomes tecnicos recentes reportados pelo backend.
  success:            { color: 'var(--ma-success)',  icon: 'check',   label: 'sucesso' },
  captcha:            { color: 'var(--ma-danger)',   icon: 'warning', label: 'captcha' },
  blocked:            { color: 'var(--ma-danger)',   icon: 'warning', label: 'bloqueado' },
  domain_circuit_open:{ color: 'var(--ma-warning)',  icon: 'clock',   label: 'circuit aberto' },
  timeout:            { color: 'var(--ma-warning)',  icon: 'clock',   label: 'timeout' },
  price_not_found:    { color: 'var(--ma-fg-muted)', icon: 'warning', label: 'preÃ§o nÃ£o encontrado' },
  rate_limited:       { color: 'var(--ma-warning)',  icon: 'warning', label: 'rate limit' },
};

function CollectionDiagnostic({ productId }) {
  const [open, setOpen] = React.useState(false);
  const [health, setHealth] = React.useState(null);
  const [loading, setLoading] = React.useState(false);

  const load = async () => {
    // Lazy load evita consultar health para todo produto listado.
    if (health || loading) return;
    setLoading(true);
    try {
      const r = await fetch(`/api/v1/monitored/${productId}/health`);
      if (r.ok) setHealth(await r.json());
    } finally {
      setLoading(false);
    }
  };

  const toggle = () => {
    if (!open) load();
    setOpen(o => !o);
  };

  const circuitOpen = health && health.circuit_state === 'OPEN';
  // Circuit breaker aberto explica ausencia temporaria de novas coletas.

  return (
    <div style={{marginTop: 12, borderRadius: 10, border: '1px solid var(--ma-neutral-600)', overflow: 'hidden'}}>
      <button
        onClick={toggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 16px', background: 'var(--ma-neutral-700)', border: 'none',
          cursor: 'pointer', color: 'var(--ma-fg)', fontFamily: 'var(--ma-font-mono)',
          fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
        }}
      >
        <Icon name="zap" size={12} color="var(--ma-fg-muted)"/>
        <span style={{flex: 1, textAlign: 'left'}}>DiagnÃ³stico de Coleta</span>
        {health && circuitOpen && (
          <span style={{fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'var(--ma-danger)', color: '#fff', fontWeight: 800}}>
            CIRCUIT OPEN Â· {health.circuit_cooldown_seconds}s
          </span>
        )}
        {health && !circuitOpen && (
          <span style={{fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'var(--ma-success)', color: '#fff', fontWeight: 800}}>
            CIRCUIT CLOSED
          </span>
        )}
        <Icon name={open ? 'chevron-up' : 'chevron-down'} size={12} color="var(--ma-fg-muted)"/>
      </button>

      {open && (
        <div style={{padding: '12px 16px', background: 'var(--ma-neutral-800)'}}>
          {loading && <div style={{color: 'var(--ma-fg-subtle)', fontSize: 12}}>Carregandoâ€¦</div>}
          {health && (
            <>
              <div style={{display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 12}}>
                <div>
                  <div style={{fontSize: 10, color: 'var(--ma-fg-subtle)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2}}>DomÃ­nio</div>
                  <div style={{fontFamily: 'var(--ma-font-mono)', fontSize: 12, color: 'var(--ma-fg)'}}>{health.domain}</div>
                </div>
                <div>
                  <div style={{fontSize: 10, color: 'var(--ma-fg-subtle)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2}}>Ãšltima coleta bem-sucedida</div>
                  <div style={{fontFamily: 'var(--ma-font-mono)', fontSize: 12, color: 'var(--ma-fg)'}}>{health.last_successful_collection_at || 'â€”'}</div>
                </div>
              </div>
              {health.recent_attempts.length > 0 ? (
                <div style={{display: 'flex', flexDirection: 'column', gap: 4}}>
                  <div style={{fontSize: 10, color: 'var(--ma-fg-subtle)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4}}>Ãšltimas tentativas</div>
                  {health.recent_attempts.map((a, i) => {
                    const s = OUTCOME_STYLE[a.outcome] || { color: 'var(--ma-fg-muted)', icon: 'warning', label: a.outcome };
                    return (
                      <div key={i} style={{display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderTop: i > 0 ? '1px solid var(--ma-neutral-600)' : 'none'}}>
                        <Icon name={s.icon} size={12} color={s.color}/>
                        <span style={{fontFamily: 'var(--ma-font-mono)', fontSize: 11, color: s.color, minWidth: 140}}>{s.label}</span>
                        <span style={{fontFamily: 'var(--ma-font-mono)', fontSize: 10, color: 'var(--ma-fg-subtle)'}}>{a.ts}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{fontSize: 12, color: 'var(--ma-fg-subtle)'}}>Nenhuma tentativa registrada.</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

Object.assign(window, { CollectionDiagnostic });
