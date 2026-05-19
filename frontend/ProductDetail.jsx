/* global React, Icon, Button, IconButton, VariationBadge, Card, Tag, StatusDot, ComparisonBadge, MarketplaceChip, brl */

function PriceChart({ data, height = 220 }) {
  if (!data || data.length < 2) {
    return (
      <div style={{height, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--ma-fg-subtle)', fontSize: 12, gap: 8}}>
        <Icon name="warning" size={14}/>
        Sem histórico de preços ainda.
      </div>
    );
  }
  const W = 720, H = height, PADX = 12, PADY = 24;
  const min = Math.min(...data), max = Math.max(...data);
  const range = (max - min) || max * 0.05 || 1;
  const yMin = min - range * 0.15, yMax = max + range * 0.15;
  const yRange = yMax - yMin;
  const step = (W - PADX * 2) / (data.length - 1);
  const pts = data.map((v, i) => [PADX + i * step, PADY + (1 - (v - yMin) / yRange) * (H - PADY * 2)]);
  const path = 'M ' + pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' L ');
  const fillPath = path + ` L ${pts[pts.length-1][0]},${H-PADY} L ${pts[0][0]},${H-PADY} Z`;
  const last = pts[pts.length-1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none">
      <defs>
        <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FF7A1A" stopOpacity="0.35"/>
          <stop offset="1" stopColor="#FF7A1A" stopOpacity="0"/>
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((p, i) => (
        <line key={i} x1={PADX} x2={W-PADX} y1={PADY + p*(H-PADY*2)} y2={PADY + p*(H-PADY*2)}
          stroke="rgba(255,255,255,0.05)" strokeDasharray="2 4"/>
      ))}
      <path d={fillPath} fill="url(#chartFill)"/>
      <path d={path} fill="none" stroke="#FF7A1A" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx={last[0]} cy={last[1]} r="4" fill="#FF7A1A"/>
      <circle cx={last[0]} cy={last[1]} r="9" fill="#FF7A1A" opacity="0.18"/>
      <text x={PADX} y={14} fill="rgba(255,255,255,0.5)" fontSize="10" fontFamily="JetBrains Mono">{'R$ ' + max.toFixed(2).replace('.', ',')}</text>
      <text x={PADX} y={H-6} fill="rgba(255,255,255,0.5)" fontSize="10" fontFamily="JetBrains Mono">{'R$ ' + min.toFixed(2).replace('.', ',')}</text>
    </svg>
  );
}

const NEXT_CHECK_REASON_LABEL = {
  price_changed:        'preço variou — frequência aumentada',
  recurring:            'ciclo automático regular',
  stable_backoff:       'preço estável — frequência reduzida',
  retry_backoff:        'retry após falha de coleta',
  manual:               'enfileirado manualmente',
  domain_blocked:       'domínio bloqueado — aguardando cooldown',
  domain_circuit_open:  'domínio bloqueado — circuito aberto',
};

const STABILITY_LABEL = {
  unstable:    'instável',
  stable:      'estável',
  very_stable: 'muito estável',
};

function CollectField({ label, value, icon, highlight }) {
  return (
    <div style={{display:'flex', alignItems:'center', gap: 8}}>
      <Icon name={icon} size={14} color={highlight ? 'var(--ma-brand-primary)' : 'var(--ma-fg-muted)'}/>
      <div>
        <div style={{fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--ma-fg-subtle)'}}>{label}</div>
        <div style={{fontFamily: 'var(--ma-font-mono)', fontSize: 12, color: highlight ? 'var(--ma-fg-strong)' : 'var(--ma-fg)', fontWeight: 600, marginTop: 2}}>{value || '—'}</div>
      </div>
    </div>
  );
}

const OUTCOME_STYLE = {
  success:            { color: 'var(--ma-success)',  icon: 'check',   label: 'sucesso' },
  captcha:            { color: 'var(--ma-danger)',   icon: 'warning', label: 'captcha' },
  blocked:            { color: 'var(--ma-danger)',   icon: 'warning', label: 'bloqueado' },
  domain_circuit_open:{ color: 'var(--ma-warning)',  icon: 'clock',   label: 'circuit aberto' },
  timeout:            { color: 'var(--ma-warning)',  icon: 'clock',   label: 'timeout' },
  price_not_found:    { color: 'var(--ma-fg-muted)', icon: 'warning', label: 'preço não encontrado' },
  rate_limited:       { color: 'var(--ma-warning)',  icon: 'warning', label: 'rate limit' },
};

function CollectionDiagnostic({ productId }) {
  const [open, setOpen] = React.useState(false);
  const [health, setHealth] = React.useState(null);
  const [loading, setLoading] = React.useState(false);

  const load = async () => {
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
        <span style={{flex: 1, textAlign: 'left'}}>Diagnóstico de Coleta</span>
        {health && circuitOpen && (
          <span style={{fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'var(--ma-danger)', color: '#fff', fontWeight: 800}}>
            CIRCUIT OPEN · {health.circuit_cooldown_seconds}s
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
          {loading && <div style={{color: 'var(--ma-fg-subtle)', fontSize: 12}}>Carregando…</div>}
          {health && (
            <>
              <div style={{display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 12}}>
                <div>
                  <div style={{fontSize: 10, color: 'var(--ma-fg-subtle)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2}}>Domínio</div>
                  <div style={{fontFamily: 'var(--ma-font-mono)', fontSize: 12, color: 'var(--ma-fg)'}}>{health.domain}</div>
                </div>
                <div>
                  <div style={{fontSize: 10, color: 'var(--ma-fg-subtle)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2}}>Última coleta bem-sucedida</div>
                  <div style={{fontFamily: 'var(--ma-font-mono)', fontSize: 12, color: 'var(--ma-fg)'}}>{health.last_successful_collection_at || '—'}</div>
                </div>
              </div>
              {health.recent_attempts.length > 0 ? (
                <div style={{display: 'flex', flexDirection: 'column', gap: 4}}>
                  <div style={{fontSize: 10, color: 'var(--ma-fg-subtle)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4}}>Últimas tentativas</div>
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

function AddCompetitorInline({ productId, onAdded }) {
  const [open, setOpen] = React.useState(false);
  const [url, setUrl] = React.useState('');
  const [name, setName] = React.useState('');
  const [saving, setSaving] = React.useState(false);
  const [err, setErr] = React.useState(null);

  const submit = async () => {
    if (!url.trim()) return;
    setSaving(true); setErr(null);
    try {
      const r = await fetch(`/api/v1/monitored/${productId}/competitors`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim(), name: name.trim() || null }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      setUrl(''); setName(''); setOpen(false);
      onAdded && onAdded();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return <Button kind="primary" leading="plus" size="sm" onClick={() => setOpen(true)}>Adicionar concorrente</Button>;
  }

  return (
    <div style={{display:'flex', alignItems:'center', gap: 8, flexWrap:'wrap'}}>
      <div className={`ma-input ${err ? 'is-error' : ''}`} style={{height: 32, flex: '1 1 260px', minWidth: 200}}>
        <Icon name="link" size={14}/>
        <input value={url} onChange={e => setUrl(e.target.value)} placeholder="URL do concorrente" onKeyDown={e => e.key === 'Enter' && submit()}/>
      </div>
      <div className="ma-input" style={{height: 32, flex: '0 1 160px'}}>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Nome (opcional)" onKeyDown={e => e.key === 'Enter' && submit()}/>
      </div>
      <Button kind="primary" size="sm" leading="check" onClick={submit} disabled={saving}>{saving ? 'Salvando…' : 'Adicionar'}</Button>
      <Button kind="ghost" size="sm" onClick={() => { setOpen(false); setErr(null); }}>Cancelar</Button>
      {err && <span style={{fontSize: 11, color: 'var(--ma-danger)', width: '100%'}}>{err}</span>}
    </div>
  );
}

function ProductDetail({ product, onBack, onRefresh }) {
  const [range, setRange] = React.useState('30');
  const [paused, setPaused] = React.useState(product.status === 'paused');
  const [toggling, setToggling] = React.useState(false);

  if (!product) return null;

  const cmp = product.latest_comparison;
  const competitors = product.competitors || [];
  const isPaused = paused;
  const effectiveStatus = isPaused ? 'paused' : product.status;
  const hasError = product.status === 'error';

  const togglePause = async () => {
    setToggling(true);
    try {
      const action = isPaused ? 'resume' : 'pause';
      const r = await fetch(`/api/v1/monitored/${product.id}/${action}`, { method: 'PATCH' });
      if (r.ok) {
        setPaused(!isPaused);
        onRefresh && onRefresh();
      }
    } finally {
      setToggling(false);
    }
  };

  const deleteProduct = async () => {
    if (!confirm(`Excluir "${product.name}"? Esta ação não pode ser desfeita.`)) return;
    const r = await fetch(`/api/v1/monitored/${product.id}`, { method: 'DELETE' });
    if (r.ok || r.status === 204) onBack();
  };

  const deleteCompetitor = async (cId) => {
    if (!confirm('Excluir este concorrente?')) return;
    await fetch(`/api/v1/competitors/${cId}`, { method: 'DELETE' });
    onRefresh && onRefresh();
  };

  return (
    <div>
      {/* Header actions */}
      <div style={{display:'flex', alignItems:'center', gap: 10, marginBottom: 6, flexWrap:'wrap'}}>
        <Button kind="ghost" leading="chevron-left" onClick={onBack} size="sm">Voltar</Button>
        <div style={{flex: 1}}/>
        <AddCompetitorInline productId={product.id} onAdded={onRefresh}/>
        <Button kind="secondary" leading={isPaused ? 'play' : 'pause'} size="sm" onClick={togglePause} disabled={toggling}>
          {isPaused ? 'Retomar' : 'Pausar'}
        </Button>
        <Button kind="secondary" leading="external" size="sm" onClick={() => window.open(product.url_original, '_blank')}>Ver anúncio</Button>
        <Button kind="danger" leading="trash" size="sm" onClick={deleteProduct}>Excluir</Button>
      </div>

      {/* Title block */}
      <div style={{display:'flex', alignItems:'flex-start', gap: 14, marginBottom: 22}}>
        <div style={{width: 48, height: 48, borderRadius: 10, background: 'var(--ma-neutral-500)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink: 0, border: '1px solid var(--ma-border)', overflow: 'hidden'}}>
          {product.thumbnail_url ? (
            <img src={product.thumbnail_url} alt={product.name} style={{width:'100%', height:'100%', objectFit:'cover'}} onError={(e) => { e.currentTarget.style.display='none'; }}/>
          ) : (
            <Icon name={product.icon || 'package'} size={22} color="var(--ma-fg-muted)"/>
          )}
        </div>
        <div style={{minWidth: 0, flex: 1}}>
          <div style={{display:'flex', alignItems:'baseline', gap: 12, flexWrap:'wrap'}}>
            <h1 style={{fontFamily:'var(--ma-font-display)', fontSize: 24, fontWeight: 800, color: 'var(--ma-fg-strong)', margin: 0, letterSpacing: '-0.02em', lineHeight: 1.15}}>{product.name}</h1>
            {cmp && !isPaused && !hasError && <ComparisonBadge status={cmp.status}/>}
            {isPaused && <Tag tone="muted">Pausado</Tag>}
            {hasError && <Tag tone="muted">Em erro</Tag>}
          </div>
          <div style={{display:'flex', alignItems:'center', gap: 12, marginTop: 8, fontSize: 12, color: 'var(--ma-fg-muted)', flexWrap:'wrap'}}>
            <MarketplaceChip marketplace={product.marketplace} size="sm"/>
            <span style={{display:'inline-flex', alignItems:'center', gap: 5}}><Icon name="clock" size={12}/>última coleta {product.last_checked_at}</span>
            <span style={{opacity: 0.4}}>·</span>
            <span style={{display:'inline-flex', alignItems:'center', gap: 5, fontFamily: 'var(--ma-font-mono)'}}>id: {product.id}</span>
          </div>
        </div>
      </div>

      {/* Error banner */}
      {hasError && (
        <div style={{display:'flex', alignItems:'center', gap: 12, padding: '12px 16px', marginBottom: 16, background: 'rgba(224,73,73,0.10)', border: '1px solid rgba(224,73,73,0.35)', borderRadius: 'var(--ma-radius-md)'}}>
          <Icon name="warning" size={18} color="var(--ma-danger)"/>
          <div style={{flex: 1, fontSize: 13}}>
            <b style={{color: 'var(--ma-fg-strong)'}}>Última coleta falhou</b> ·
            tentativas consecutivas: <span style={{fontFamily:'var(--ma-font-mono)', color:'var(--ma-fg-strong)', fontWeight: 600}}>{product.consecutive_failures}</span> ·
            próxima tentativa <span style={{fontFamily:'var(--ma-font-mono)', color:'var(--ma-fg-strong)', fontWeight: 600}}>{product.next_check_at || '—'}</span>
          </div>
        </div>
      )}

      {/* Chart + Market comparison */}
      <div style={{display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 16}}>
        <div className="ma-chart">
          <div className="ma-chart-head">
            <div className="left">
              <div className="label">
                {product.is_price_stale ? 'Último preço válido · seu produto' : 'Preço atual · seu produto'}
              </div>
              <div className="value" style={product.is_price_stale ? {color: 'var(--ma-fg-muted)'} : {}}>
                {brl(product.current_price)}
              </div>
              {product.is_price_stale && (
                <div style={{fontSize: 11, color: 'var(--ma-danger)', display: 'flex', alignItems: 'center', gap: 4, marginTop: 2}}>
                  <Icon name="warning" size={11}/>
                  dado obsoleto · coletado em {product.last_successful_collection_at || product.last_checked_at || '—'}
                </div>
              )}
              <div className="delta">
                {!product.is_price_stale && <VariationBadge value={product.variation_24h}/>}
                {product.previous_price != null && !product.is_price_stale && (
                  <span>vs. <span style={{fontFamily: 'var(--ma-font-mono)'}}>{brl(product.previous_price)}</span> (24h)</span>
                )}
              </div>
            </div>
            <div className="right">
              {['7', '30', '90'].map(r => (
                <button key={r} className={`ma-chip ${range === r ? 'is-active' : ''}`} onClick={() => setRange(r)}>{r} dias</button>
              ))}
            </div>
          </div>
          <PriceChart data={product.history}/>
        </div>

        <Card>
          <div className="ma-eyebrow">Comparação com o mercado</div>
          {cmp ? (
            <>
              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 14}}>
                {(() => {
                  const rankingValido = cmp.run_status !== 'no_competitors'
                    && cmp.run_status !== 'expired'
                    && (cmp.valid_competitors_count || 0) > 0;
                  return (
                    <div>
                      <div className="ma-kpi-label" style={{display:'flex', alignItems:'center', gap: 6}}>
                        Sua posição
                        {cmp.run_status === 'partial' && (
                          <Tag tone="warning" size="xs">rodada parcial</Tag>
                        )}
                      </div>
                      {rankingValido ? (
                        <>
                          <div className="ma-kpi-value" style={{fontSize: 28, color: cmp.ranking === 1 ? 'var(--ma-success)' : 'var(--ma-fg-strong)'}}>
                            #{cmp.ranking}<span style={{fontSize: 14, color: 'var(--ma-fg-muted)', fontWeight: 500}}> de {cmp.participants_count || '?'}</span>
                          </div>
                          <div className="ma-kpi-sub">
                            {cmp.ranking === 1
                              ? 'menor preço do mercado'
                              : `${cmp.ranking - 1} concorrente${cmp.ranking - 1 > 1 ? 's' : ''} mais barato${cmp.ranking - 1 > 1 ? 's' : ''}`}
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="ma-kpi-value" style={{fontSize: 28, color: 'var(--ma-fg-muted)'}}>— / —</div>
                          <div className="ma-kpi-sub" style={{color: 'var(--ma-fg-subtle)'}}>
                            {cmp.run_status === 'no_competitors' ? 'sem concorrentes na rodada' : 'dados insuficientes'}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })()}
                <div>
                  <div className="ma-kpi-label">Preço médio</div>
                  <div className="ma-kpi-value" style={{fontSize: 28}}>{brl(cmp.average_price)}</div>
                  <div className="ma-kpi-sub">
                    {product.current_price != null && cmp.average_price != null && (
                      product.current_price < cmp.average_price
                        ? `você está ${((1 - product.current_price / cmp.average_price) * 100).toFixed(1).replace('.', ',')}% abaixo`
                        : `você está ${((product.current_price / cmp.average_price - 1) * 100).toFixed(1).replace('.', ',')}% acima`
                    )}
                  </div>
                </div>
              </div>
              <div className="ma-divider"/>
              <div style={{display:'flex', gap: 20, fontSize: 12, flexWrap:'wrap'}}>
                <div>
                  <span className="ma-meta">menor</span>
                  <div style={{fontFamily:'var(--ma-font-mono)', color:'var(--ma-success)', fontWeight: 600}}>{brl(cmp.min_price)}</div>
                </div>
                <div>
                  <span className="ma-meta">maior</span>
                  <div style={{fontFamily:'var(--ma-font-mono)', color:'var(--ma-danger)', fontWeight: 600}}>{brl(cmp.max_price)}</div>
                </div>
                <div style={{marginLeft: 'auto'}}>
                  <span className="ma-meta">rodada</span>
                  <div style={{fontFamily:'var(--ma-font-mono)', color:'var(--ma-fg-strong)', fontWeight: 600, textTransform: 'lowercase'}}>{cmp.run_status || '—'} · {cmp.valid_competitors_count || 0}/{(cmp.participants_count || 1) - 1}</div>
                </div>
              </div>
              {cmp.potential_adjustment != null && (
                <div style={{marginTop: 14, padding: 12, background: 'rgba(255,196,0,0.06)', borderRadius: 'var(--ma-radius-sm)', border: '1px solid rgba(255,196,0,0.18)'}}>
                  <div className="ma-eyebrow" style={{color: 'var(--ma-brand-secondary)', marginBottom: 4}}>Ajuste sugerido</div>
                  <div style={{fontSize: 13, color: 'var(--ma-fg)', lineHeight: 1.5}}>
                    Reduzir <b style={{fontFamily:'var(--ma-font-mono)', color: 'var(--ma-brand-secondary)'}}>{brl(Math.abs(Number(cmp.potential_adjustment)))}</b> levaria você a <b style={{color: 'var(--ma-fg-strong)'}}>#{Math.max(1, cmp.ranking - 3)}</b>.
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{padding: '24px 4px', textAlign: 'center', color: 'var(--ma-fg-muted)', fontSize: 12}}>
              <Icon name="warning" size={24} color="var(--ma-fg-subtle)"/>
              <div style={{marginTop: 8}}>Comparação ainda não calculada para este produto.</div>
            </div>
          )}
        </Card>
      </div>

      {/* Collection strip */}
      <Card className="ma-collect-strip" style={{marginTop: 16, padding: '12px 18px'}}>
        <div style={{display:'flex', alignItems:'center', gap: 24, flexWrap:'wrap'}}>
          <StatusDot status={effectiveStatus}/>
          <CollectField label="Última coleta" value={product.last_checked_at} icon="refresh"/>
          <CollectField label="Próxima coleta" value={isPaused ? '—' : (product.next_check_at || '—')} icon="clock" highlight={!isPaused}/>
          <CollectField label="Intervalo atual" value={`${product.check_interval_minutes} min`} icon="calendar"/>
          <CollectField label="Estabilidade" value={STABILITY_LABEL[product.stability_level] || (product.stability_level || '—')} icon="target"/>
          {product.next_check_reason && (
            <CollectField label="Motivo" value={NEXT_CHECK_REASON_LABEL[product.next_check_reason] || product.next_check_reason} icon="zap"/>
          )}
        </div>
      </Card>

      {/* Collection diagnostic */}
      <CollectionDiagnostic productId={product.id}/>

      {/* Competitors */}
      {competitors.length > 0 && (
        <>
          <div className="ma-section-head">
            <h2>Concorrentes</h2>
            <span className="ma-section-meta">{competitors.length} fonte{competitors.length !== 1 ? 's' : ''} monitorada{competitors.length !== 1 ? 's' : ''} · ordenado por preço</span>
          </div>
          <Card padded={false}>
            {[...competitors].sort((a, b) => (a.current_price || 0) - (b.current_price || 0)).map((c, i) => {
              const myPrice = product.current_price || 0;
              const diff = (c.current_price || 0) - myPrice;
              const diffPct = myPrice ? (diff / myPrice) * 100 : 0;
              const isBelow = diff < 0;
              return (
                <div key={c.id} className="ma-comp-row ma-comp-row-detailed">
                  <div className={`ma-comp-dot ${isBelow ? 'below' : 'above'}`}/>
                  <div style={{minWidth: 0}}>
                    <div style={{display:'flex', alignItems:'center', gap: 8, flexWrap:'wrap'}}>
                      <span className="ma-comp-name">{c.name || 'Concorrente'}</span>
                      <span style={{fontSize: 10, color: 'var(--ma-fg-subtle)', fontFamily: 'var(--ma-font-mono)', background: 'var(--ma-neutral-500)', padding: '1px 6px', borderRadius: 4}}>#{i + 1}</span>
                      <MarketplaceChip marketplace={c.marketplace} size="sm"/>
                    </div>
                    <div className="ma-comp-seen">coletado {c.last_checked_at} · {isBelow ? 'abaixo do seu preço' : 'acima do seu preço'}</div>
                  </div>
                  <div className="ma-comp-price">{brl(c.current_price)}</div>
                  <div><VariationBadge value={c.variation_24h}/></div>
                  <div className={`ma-comp-diff ${isBelow ? 'above' : 'below'}`}>
                    {diff > 0 ? '+' : '−'}{brl(Math.abs(diff)).replace('R$ ', 'R$ ')}
                    <div style={{fontSize: 10, opacity: 0.7}}>{diff > 0 ? '+' : '−'}{Math.abs(diffPct).toFixed(1).replace('.', ',')}%</div>
                  </div>
                  <div style={{display:'flex', gap: 4, justifyContent:'flex-end'}}>
                    <IconButton name="external" size="sm" title="Ver anúncio" onClick={() => window.open(c.url_original, '_blank')}/>
                    <IconButton name="trash" size="sm" title="Excluir concorrente" onClick={() => deleteCompetitor(c.id)}/>
                  </div>
                </div>
              );
            })}
          </Card>
        </>
      )}
    </div>
  );
}

Object.assign(window, { ProductDetail });
