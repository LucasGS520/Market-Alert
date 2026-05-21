/* global React, Icon, Button, IconButton, VariationBadge, Card, Tag, StatusDot, ComparisonBadge, MarketplaceChip, PriceChart, CollectionDiagnostic, AddCompetitorInline, brl */
// Tela de detalhe: combina estado duravel do produto, comparacao e diagnostico operacional.
const NEXT_CHECK_REASON_LABEL = {
  // Labels de motivos de agendamento calculados pelo backend.
  price_changed:        'preço variou — frequência aumentada',
  recurring:            'ciclo automático regular',
  stable_backoff:       'preço estável — frequência reduzida',
  retry_backoff:        'retry após falha de coleta',
  manual:               'enfileirado manualmente',
  domain_blocked:       'domínio bloqueado — aguardando cooldown',
  domain_circuit_open:  'domínio bloqueado — circuito aberto',
};

const STABILITY_LABEL = {
  // Traducao visual da estabilidade observada nas ultimas coletas.
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
    // Pause/resume altera elegibilidade de coleta, mas a UI atualiza depois via onRefresh.
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
    // Delete remove o produto duravel; ao concluir, a tela volta para a lista.
    if (!confirm(`Excluir "${product.name}"? Esta ação não pode ser desfeita.`)) return;
    const r = await fetch(`/api/v1/monitored/${product.id}`, { method: 'DELETE' });
    if (r.ok || r.status === 204) onBack();
  };

  const deleteCompetitor = async (cId) => {
    // Remover concorrente invalida a comparacao atual e o backend recalcula depois.
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
                  // Ranking so e confiavel quando a rodada teve concorrentes validos.
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
              // Diferenca e calculada contra o preco atual do produto monitorado.
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
