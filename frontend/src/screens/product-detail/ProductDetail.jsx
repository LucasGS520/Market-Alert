/* global React, Icon, Button, IconButton, VariationBadge, Card, Tag, StatusDot, ComparisonBadge, MarketplaceChip, PriceChart, CollectionDiagnostic, AddCompetitorInline, brl */
// Tela de detalhe: combina estado duravel do produto, comparacao e diagnostico operacional.
const NEXT_CHECK_REASON_LABEL = {
  success_price_changed:   'preço variou — frequência aumentada',
  success_price_unchanged: 'preço sem variação — intervalo regular',
  error_backoff:           'retry após falha de coleta',
  unavailable:             'produto indisponível — aguardando retomada',
  unsupported:             'marketplace sem suporte de coleta',
  initial:                 'primeiro agendamento',
};

const STABILITY_LABEL = {
  // Traducao visual da estabilidade observada nas ultimas coletas.
  unstable:    'instável',
  stable:      'estável',
  very_stable: 'muito estável',
};

const RUN_STATUS_LABEL = {
  complete:       'Completa',
  partial:        'Parcial',
  expired:        'Expirada',
  no_competitors: 'Sem concorrentes',
  manual:         'Manual',
  pending:        'Pendente',
};

function Tooltip({ content, children }) {
  const [show, setShow] = React.useState(false);
  return (
    <div style={{position:'relative', display:'inline-flex'}}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <div style={{
          position:'absolute', bottom:'calc(100% + 6px)', left:'50%', transform:'translateX(-50%)',
          background:'#1e1e2e', border:'1px solid var(--ma-border)', borderRadius:6,
          padding:'6px 10px', fontSize:11, color:'var(--ma-fg)', whiteSpace:'nowrap',
          zIndex:200, pointerEvents:'none', boxShadow:'0 4px 12px rgba(0,0,0,0.5)', lineHeight:1.5,
        }}>
          {content}
        </div>
      )}
    </div>
  );
}

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

      {/* Chart + Market comparison — produto estreito à esquerda, mercado largo à direita */}
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 16}}>

        {/* ESQUERDA (estreito): Seu produto — preço, variações, posição, ajuste */}
        <Card>
          <div className="ma-eyebrow">Seu produto</div>
          <div style={{marginTop: 10}}>
            <div style={{fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: product.is_price_stale ? 'var(--ma-fg-muted)' : 'var(--ma-fg-subtle)'}}>
              {product.is_price_stale ? 'Último preço válido' : 'Preço atual'}
            </div>
            <div style={{fontFamily: 'var(--ma-font-display)', fontSize: 32, fontWeight: 800, letterSpacing: '-0.02em', color: product.is_price_stale ? 'var(--ma-fg-muted)' : 'var(--ma-fg-strong)', marginTop: 2}}>
              {brl(product.current_price)}
            </div>
            {product.is_price_stale && (
              <div style={{fontSize: 11, color: 'var(--ma-danger)', display: 'flex', alignItems: 'center', gap: 4, marginTop: 4}}>
                <Icon name="warning" size={11}/>
                dado obsoleto · coletado em {product.last_successful_collection_at || product.last_checked_at || '—'}
              </div>
            )}
            {!product.is_price_stale && (
              <div style={{marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4}}>
                {(product.variation_since_previous != null || product.previous_price != null) && (
                  <div style={{display: 'flex', alignItems: 'center', gap: 6, fontSize: 12}}>
                    <VariationBadge value={product.variation_since_previous}/>
                    {product.previous_price != null && (
                      <span style={{color: 'var(--ma-fg-muted)'}}>vs. <span style={{fontFamily: 'var(--ma-font-mono)'}}>{brl(product.previous_price)}</span></span>
                    )}
                  </div>
                )}
                <div style={{display: 'flex', alignItems: 'center', gap: 6, fontSize: 11}}>
                  <Tooltip content="Variação acumulada desde a primeira coleta registrada para este produto.">
                    <VariationBadge value={product.variation_since_start}/>
                  </Tooltip>
                </div>
              </div>
            )}
          </div>
          {cmp && (
            <>
              <div className="ma-divider"/>
              {(() => {
                // Ranking só é exibido quando a referência participou do snapshot
                // e a rodada teve concorrentes válidos suficientes.
                const rankingValido = cmp.reference_available !== false
                  && cmp.ranking != null
                  && cmp.run_status !== 'no_competitors'
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
                          {cmp.reference_available === false
                            ? 'oferta de referência indisponível'
                            : cmp.run_status === 'no_competitors'
                            ? 'sem concorrentes na rodada'
                            : 'dados insuficientes'}
                        </div>
                      </>
                    )}
                  </div>
                );
              })()}
              {/* Insight de gap vs. média — leitura derivada, não KPI principal */}
              {product.current_price != null && cmp.average_price != null && (
                <div style={{fontSize: 12, color: 'var(--ma-fg-muted)', marginTop: 8}}>
                  {product.current_price < cmp.average_price
                    ? `Você está ${((1 - product.current_price / cmp.average_price) * 100).toFixed(1).replace('.', ',')}% abaixo da média do mercado.`
                    : product.current_price > cmp.average_price
                    ? `Você está ${((product.current_price / cmp.average_price - 1) * 100).toFixed(1).replace('.', ',')}% acima da média do mercado.`
                    : 'Você está na média do mercado.'}
                </div>
              )}
              {cmp.reference_available === false && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 12px', marginTop: 10,
                  background: 'rgba(255,196,0,0.07)',
                  border: '1px solid rgba(255,196,0,0.18)',
                  borderRadius: 'var(--ma-radius-sm)',
                  fontSize: 11, color: 'var(--ma-fg-muted)',
                }}>
                  <Icon name="eye" size={12} color="var(--ma-warning)"/>
                  Seu produto não participou desta rodada — mercado calculado com {cmp.valid_competitors_count || 0} concorrente(s)
                </div>
              )}
              {cmp.potential_adjustment != null && (
                <div style={{marginTop: 14, padding: 12, background: 'rgba(255,196,0,0.06)', borderRadius: 'var(--ma-radius-sm)', border: '1px solid rgba(255,196,0,0.18)'}}>
                  <div className="ma-eyebrow" style={{color: 'var(--ma-brand-secondary)', marginBottom: 4}}>Ajuste sugerido</div>
                  <div style={{fontSize: 13, color: 'var(--ma-fg)', lineHeight: 1.5}}>
                    Reduzir <b style={{fontFamily:'var(--ma-font-mono)', color: 'var(--ma-brand-secondary)'}}>{brl(Math.abs(Number(cmp.potential_adjustment)))}</b> levaria você a <b style={{color: 'var(--ma-fg-strong)'}}>#{Math.max(1, cmp.ranking - 3)}</b>.
                  </div>
                </div>
              )}
            </>
          )}
        </Card>

        {/* DIREITA (largo): Mercado monitorado — 3 zonas: cabeçalho, KPIs, histórico */}
        <Card>
          {/* Zona 1 — Cabeçalho operacional */}
          <div style={{display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap: 12, flexWrap:'wrap'}}>
            <div>
              <div className="ma-eyebrow" style={{marginBottom: 2}}>Mercado monitorado</div>
              <div style={{fontSize: 11, color:'var(--ma-fg-subtle)'}}>desde o início do monitoramento</div>
            </div>
            {cmp && (
              <div style={{
                fontSize: 11, fontFamily:'var(--ma-font-mono)', fontWeight: 600, textAlign:'right',
                color: (cmp.run_status === 'partial' || cmp.run_status === 'expired')
                  ? 'var(--ma-warning)' : 'var(--ma-fg-muted)',
              }}>
                {RUN_STATUS_LABEL[cmp.run_status] || cmp.run_status || '—'}
                {' · '}
                {cmp.valid_competitors_count || 0}/{(cmp.participants_count || 1) - 1} concorrentes
              </div>
            )}
          </div>

          {/* Zona 2 — KPIs horizontais iguais */}
          {cmp ? (
            <>
              <div className="ma-divider"/>
              <div style={{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap: 0}}>
                {[
                  { label: 'Menor preço', value: cmp.min_price, color: 'var(--ma-success)', variation: product.market_min_variation_since_start },
                  { label: 'Preço médio', value: cmp.average_price, color: 'var(--ma-fg-strong)', variation: null },
                  { label: 'Maior preço', value: cmp.max_price, color: 'var(--ma-danger)', variation: null },
                ].map(({ label, value, color, variation }, i) => (
                  <div key={label} style={{
                    padding: '8px 12px',
                    borderLeft: i > 0 ? '1px solid var(--ma-border)' : 'none',
                  }}>
                    <div style={{fontSize: 10, fontWeight: 700, letterSpacing:'0.06em', textTransform:'uppercase', color:'var(--ma-fg-subtle)', marginBottom: 4}}>
                      {label}
                    </div>
                    <div style={{fontFamily:'var(--ma-font-mono)', fontSize: 17, fontWeight: 700, color, letterSpacing:'-0.01em'}}>
                      {brl(value)}
                    </div>
                    {variation != null && (
                      <div style={{marginTop: 4}}>
                        <Tooltip content="Variação do menor preço de mercado desde o início do monitoramento deste produto.">
                          <VariationBadge value={variation}/>
                        </Tooltip>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{padding: '16px 4px', textAlign: 'center', color: 'var(--ma-fg-muted)', fontSize: 12}}>
              <Icon name="warning" size={24} color="var(--ma-fg-subtle)"/>
              <div style={{marginTop: 8}}>Comparação ainda não calculada para este produto.</div>
            </div>
          )}

          {/* Zona 3 — Histórico do monitoramento */}
          <div className="ma-divider"/>
          <div style={{marginBottom: 6}}>
            <span style={{fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--ma-fg-subtle)'}}>Histórico do monitoramento</span>
            <div style={{fontSize: 11, color:'var(--ma-fg-subtle)', marginTop: 3}}>
              Preço do produto comparado ao menor preço e à média do mercado desde a primeira coleta.
            </div>
          </div>
          <PriceChart height={280} series={[
            { id: 'product', label: 'Seu produto', color: '#FF7A1A', data: product.product_series || [] },
            ...(product.market_min_series && product.market_min_series.length >= 2 ? [{ id: 'market_min', label: 'Menor preço', color: '#2DD4BF', data: product.market_min_series }] : []),
            ...(product.market_avg_series && product.market_avg_series.length >= 2 ? [{ id: 'market_avg', label: 'Preço médio', color: '#818CF8', data: product.market_avg_series }] : []),
          ]}/>
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
              const gap = c.gap_vs_product;
              const gapPct = c.gap_vs_product_percent;
              const isBelow = gap != null ? gap < 0 : false;
              return (
                <div key={c.id} className="ma-comp-row ma-comp-row-detailed">
                  {c.thumbnail_url
                    ? <img src={c.thumbnail_url} alt="" width={26} height={26}
                           style={{borderRadius: 3, objectFit: 'cover', flexShrink: 0}}
                           onError={e => { e.currentTarget.style.display = 'none'; }}/>
                    : <div className={`ma-comp-dot ${isBelow ? 'below' : 'above'}`}/>
                  }
                  <div style={{minWidth: 0}}>
                    <div style={{display:'flex', alignItems:'center', gap: 8, flexWrap:'wrap'}}>
                      <span className="ma-comp-name">{c.name || 'Concorrente'}</span>
                      <span style={{fontSize: 10, color: 'var(--ma-fg-subtle)', fontFamily: 'var(--ma-font-mono)', background: 'var(--ma-neutral-500)', padding: '1px 6px', borderRadius: 4}}>#{i + 1}</span>
                      <MarketplaceChip marketplace={c.marketplace} size="sm"/>
                    </div>
                    <div className="ma-comp-seen">coletado {c.last_checked_at} · {gap != null ? (isBelow ? 'abaixo do seu preço' : 'acima do seu preço') : '—'}</div>
                  </div>
                  <div className="ma-comp-price">{brl(c.current_price)}</div>
                  <Tooltip content="Variação do preço deste concorrente desde a primeira coleta registrada.">
                    <VariationBadge value={c.variation_since_start}/>
                  </Tooltip>
                  <Tooltip content={gap != null
                    ? `Diferença em relação ao seu produto · ${isBelow ? `concorrente ${gapPct != null ? Math.abs(gapPct).toFixed(1).replace('.', ',') : '?'}% mais barato` : `concorrente ${gapPct != null ? Math.abs(gapPct).toFixed(1).replace('.', ',') : '?'}% mais caro`}`
                    : 'Sem dados de gap disponíveis'}>
                    <div className={`ma-comp-diff ${isBelow ? 'above' : 'below'}`}>
                      {gap != null ? (
                        <>
                          {gap > 0 ? '+' : '−'}{brl(Math.abs(gap)).replace('R$ ', 'R$ ')}
                          <div style={{fontSize: 10, opacity: 0.7}}>{gapPct != null ? `${gapPct > 0 ? '+' : '−'}${Math.abs(gapPct).toFixed(1).replace('.', ',')}%` : ''}</div>
                        </>
                      ) : '—'}
                    </div>
                  </Tooltip>
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
