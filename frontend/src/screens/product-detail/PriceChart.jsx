/* global React, Icon */
// Grafico multi-serie do detalhe do produto. Cada serie tem timestamps explícitos.
// series: [{id, label, color, data: [{t: string ISO, v: number}]}]
function PriceChart({ series, height = 220 }) {
  const [hover, setHover] = React.useState(null);
  const W = 720, PADX = 48, PADY = 20;
  const H = height;

  const activeSeries = (series || []).filter(s => Array.isArray(s.data) && s.data.length >= 1);
  const hasLines = activeSeries.some(s => s.data.length >= 2);

  if (activeSeries.length === 0) {
    return (
      <div style={{height, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--ma-fg-subtle)', fontSize: 12, gap: 8}}>
        <Icon name="warning" size={14}/>
        Aguardando primeira coleta para montar o histórico.
      </div>
    );
  }

  if (!hasLines) {
    return (
      <div style={{height, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--ma-fg-subtle)', fontSize: 12, gap: 8, flexDirection:'column'}}>
        <Icon name="warning" size={14}/>
        Histórico iniciado. O gráfico será exibido após mais uma coleta.
      </div>
    );
  }

  // Range global de tempo e preço
  let tMin = Infinity, tMax = -Infinity, vMin = Infinity, vMax = -Infinity;
  for (const s of activeSeries) {
    for (const pt of s.data) {
      const ts = new Date(pt.t).getTime();
      if (ts < tMin) tMin = ts;
      if (ts > tMax) tMax = ts;
      if (pt.v < vMin) vMin = pt.v;
      if (pt.v > vMax) vMax = pt.v;
    }
  }

  const tRange = tMax - tMin || 1;
  const vRange = (vMax - vMin) || vMax * 0.05 || 1;
  const yMin = vMin - vRange * 0.15;
  const yMax = vMax + vRange * 0.15;
  const yRange = yMax - yMin;

  const toX = (t) => PADX + ((new Date(t).getTime() - tMin) / tRange) * (W - PADX - 12);
  const toY = (v) => PADY + (1 - (v - yMin) / yRange) * (H - PADY * 2);

  const buildPath = (data) => {
    if (data.length < 2) return null;
    return 'M ' + data.map(pt => `${toX(pt.t).toFixed(1)},${toY(pt.v).toFixed(1)}`).join(' L ');
  };

  const productSeries = activeSeries[0];
  // Se o produto tem 1 único ponto, sintetiza um segundo ponto no tMax para mostrar linha horizontal
  const productData = productSeries.data.length === 1
    ? [productSeries.data[0], { t: new Date(tMax).toISOString(), v: productSeries.data[0].v }]
    : productSeries.data;
  const productPath = buildPath(productData);
  const firstPt = productData[0];
  const lastPt = productData[productData.length - 1];
  const fillPath = productPath
    ? productPath + ` L ${toX(lastPt.t).toFixed(1)},${H - PADY} L ${toX(firstPt.t).toFixed(1)},${H - PADY} Z`
    : null;

  // 4 labels no eixo Y
  const yTicks = [0, 0.33, 0.67, 1.0].map(p => ({
    p,
    v: yMax - p * yRange,
    y: PADY + p * (H - PADY * 2),
  }));

  const fmtAxis = (v) => 'R$ ' + Math.round(v).toLocaleString('pt-BR');

  // Formato eixo X
  const fmtDate = (ts) => {
    const d = new Date(ts);
    const diffDays = (tMax - tMin) / (1000 * 60 * 60 * 24);
    if (diffDays > 30) {
      return d.toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' });
    }
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  };

  // Mouse hover: encontra ponto mais próximo em cada série
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = (e.clientX - rect.left) / rect.width * W;
    const tHover = tMin + (svgX - PADX) / (W - PADX - 12) * tRange;
    const pts = activeSeries.map(s => {
      const closest = s.data.reduce((best, pt) => {
        const d = Math.abs(new Date(pt.t).getTime() - tHover);
        const bd = Math.abs(new Date(best.t).getTime() - tHover);
        return d < bd ? pt : best;
      });
      return { id: s.id, label: s.label, color: s.color, t: closest.t, v: closest.v };
    });
    const refX = toX(pts[0].t);
    setHover({ svgX: refX, screenX: e.clientX - rect.left, pts });
  };

  const handleMouseLeave = () => setHover(null);

  // Gap entre produto e menor preço no hover
  const hoverGap = hover && hover.pts.length >= 2
    ? hover.pts[0].v - hover.pts[1].v
    : null;

  // Formato moeda completo (inline, sem depender do global brl)
  const fmtBrl = (v) => v == null ? '—' : 'R$ ' + v.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');

  const fmtDateTime = (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString('pt-BR', { day:'2-digit', month:'2-digit', year:'numeric' })
      + ' ' + d.toLocaleTimeString('pt-BR', { hour:'2-digit', minute:'2-digit' });
  };

  // Produto sempre tem linha (ponto único é estendido ao tMax), outras séries precisam de 2+ pontos
  const seriesWithLines = activeSeries.filter(s => s === productSeries ? productPath : s.data.length >= 2);

  return (
    <div>
      {/* Legenda acima */}
      {seriesWithLines.length > 1 && (
        <div style={{display:'flex', gap: 14, marginBottom: 8, flexWrap:'wrap'}}>
          {seriesWithLines.map((s, i) => (
            <div key={s.id} style={{display:'flex', alignItems:'center', gap: 5, fontSize: 11, color:'var(--ma-fg-muted)'}}>
              <svg width={14} height={8}>
                <line x1={0} y1={4} x2={14} y2={4}
                  stroke={s.color}
                  strokeWidth={i === 0 ? 2 : 1.5}
                  strokeDasharray={i === 0 ? undefined : (i === 1 ? '4 2' : '2 2')}
                  strokeLinecap="round"/>
              </svg>
              {s.label}
            </div>
          ))}
        </div>
      )}

      {/* SVG com tooltip interativo */}
      <div style={{position:'relative'}}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none"
          onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave}
          style={{cursor: 'crosshair', display:'block'}}>
          <defs>
            <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={productSeries.color} stopOpacity="0.10"/>
              <stop offset="1" stopColor={productSeries.color} stopOpacity="0"/>
            </linearGradient>
          </defs>

          {/* Grade horizontal + labels eixo Y */}
          {yTicks.map(({ y, v }, i) => (
            <g key={i}>
              <line x1={PADX} x2={W - 12} y1={y} y2={y}
                stroke="rgba(255,255,255,0.06)" strokeDasharray="2 4"/>
              <text x={PADX - 4} y={y + 3} fill="rgba(255,255,255,0.35)"
                fontSize="9" fontFamily="JetBrains Mono, monospace" textAnchor="end">
                {fmtAxis(v)}
              </text>
            </g>
          ))}

          {/* Fill produto */}
          {fillPath && <path d={fillPath} fill="url(#chartFill)"/>}

          {/* Séries */}
          {activeSeries.map((s, i) => {
            const path = i === 0 ? productPath : buildPath(s.data);
            if (!path) return null;
            return (
              <path key={s.id} d={path} fill="none" stroke={s.color}
                strokeWidth={i === 0 ? 2 : 1.5}
                strokeDasharray={i === 0 ? undefined : (i === 1 ? '5 3' : '2 3')}
                strokeLinejoin="round" strokeLinecap="round" opacity={i === 0 ? 1 : 0.8}/>
            );
          })}

          {/* Marcador no último ponto real do produto */}
          {productPath && !hover && (
            <>
              <circle cx={toX(productSeries.data[productSeries.data.length - 1].t)} cy={toY(productSeries.data[productSeries.data.length - 1].v)} r="4" fill={productSeries.color}/>
              <circle cx={toX(productSeries.data[productSeries.data.length - 1].t)} cy={toY(productSeries.data[productSeries.data.length - 1].v)} r="9" fill={productSeries.color} opacity="0.15"/>
            </>
          )}

          {/* Crosshair + bolinhas no hover */}
          {hover && (
            <>
              <line x1={hover.svgX} x2={hover.svgX} y1={PADY} y2={H - PADY}
                stroke="rgba(255,255,255,0.18)" strokeWidth={1} strokeDasharray="3 3"/>
              {hover.pts.map((pt, i) => {
                const path = i === 0 ? productPath : buildPath(activeSeries[i].data);
                if (!path) return null;
                return (
                  <g key={pt.id}>
                    <circle cx={toX(pt.t)} cy={toY(pt.v)} r="4" fill={pt.color}/>
                    <circle cx={toX(pt.t)} cy={toY(pt.v)} r="8" fill={pt.color} opacity="0.20"/>
                  </g>
                );
              })}
            </>
          )}
        </svg>

        {/* Tooltip flutuante */}
        {hover && (
          <div style={{
            position: 'absolute',
            left: Math.min(hover.screenX + 14, hover.screenX > (W * 0.65) ? hover.screenX - 170 : hover.screenX + 14),
            top: 8,
            background: 'var(--ma-neutral-800, #1a1a2e)',
            border: '1px solid var(--ma-border)',
            borderRadius: 6,
            padding: '8px 12px',
            fontSize: 11,
            pointerEvents: 'none',
            zIndex: 10,
            minWidth: 160,
            boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          }}>
            <div style={{color:'var(--ma-fg-muted)', marginBottom: 6, fontFamily:'var(--ma-font-mono)', fontSize: 10}}>
              {fmtDateTime(hover.pts[0].t)}
            </div>
            {hover.pts.map(pt => (
              <div key={pt.id} style={{display:'flex', alignItems:'center', gap: 6, marginBottom: 3}}>
                <span style={{width: 8, height: 8, borderRadius: '50%', background: pt.color, flexShrink:0}}/>
                <span style={{color:'var(--ma-fg-muted)', minWidth: 80}}>{pt.label}:</span>
                <span style={{fontFamily:'var(--ma-font-mono)', color:'var(--ma-fg-strong)', fontWeight:600}}>{fmtBrl(pt.v)}</span>
              </div>
            ))}
            {hoverGap != null && (
              <div style={{marginTop: 6, paddingTop: 6, borderTop:'1px solid var(--ma-border)', fontSize:10, color:'var(--ma-fg-muted)'}}>
                Gap para menor:{' '}
                <span style={{fontFamily:'var(--ma-font-mono)', color: hoverGap > 0 ? 'var(--ma-danger)' : 'var(--ma-success)', fontWeight:600}}>
                  {fmtBrl(Math.abs(hoverGap))} {hoverGap > 0 ? 'acima' : 'abaixo'}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Eixo X — início e fim */}
      <div style={{display:'flex', justifyContent:'space-between', fontSize: 10, color:'var(--ma-fg-subtle)', marginTop: 4, paddingLeft: PADX + 'px', fontFamily:'var(--ma-font-mono)'}}>
        <span>{fmtDate(tMin)}</span>
        <span>{fmtDate(tMax)}</span>
      </div>
    </div>
  );
}

Object.assign(window, { PriceChart });
