/* global React, Icon */
// Grafico multi-serie do detalhe do produto. Cada serie tem timestamps explícitos.
// series: [{id, label, color, data: [{t: string ISO, v: number}]}]
function PriceChart({ series, height = 220 }) {
  const W = 720, PADX = 12, PADY = 24;
  const H = height;

  const activeSeries = (series || []).filter(s => Array.isArray(s.data) && s.data.length >= 1);
  const hasLines = activeSeries.some(s => s.data.length >= 2);

  if (activeSeries.length === 0) {
    return (
      <div style={{height, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--ma-fg-subtle)', fontSize: 12, gap: 8}}>
        <Icon name="warning" size={14}/>
        Aguardando primeira coleta.
      </div>
    );
  }

  if (!hasLines) {
    return (
      <div style={{height, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--ma-fg-subtle)', fontSize: 12, gap: 8, flexDirection:'column'}}>
        <Icon name="warning" size={14}/>
        Apenas uma coleta registrada.
      </div>
    );
  }

  // Calcular range global de tempo e preço
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

  const toX = (t) => PADX + ((new Date(t).getTime() - tMin) / tRange) * (W - PADX * 2);
  const toY = (v) => PADY + (1 - (v - yMin) / yRange) * (H - PADY * 2);

  const buildPath = (data) => {
    if (data.length < 2) return null;
    return 'M ' + data.map(pt => `${toX(pt.t).toFixed(1)},${toY(pt.v).toFixed(1)}`).join(' L ');
  };

  // Pegar o produto (primeira série) para o gradiente de fill
  const productSeries = activeSeries[0];
  const productPath = buildPath(productSeries.data);
  const firstPt = productSeries.data[0];
  const lastPt = productSeries.data[productSeries.data.length - 1];
  const fillPath = productPath
    ? productPath + ` L ${toX(lastPt.t).toFixed(1)},${H - PADY} L ${toX(firstPt.t).toFixed(1)},${H - PADY} Z`
    : null;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none">
        <defs>
          <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={productSeries.color} stopOpacity="0.28"/>
            <stop offset="1" stopColor={productSeries.color} stopOpacity="0"/>
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((p, i) => (
          <line key={i} x1={PADX} x2={W - PADX}
            y1={PADY + p * (H - PADY * 2)} y2={PADY + p * (H - PADY * 2)}
            stroke="rgba(255,255,255,0.05)" strokeDasharray="2 4"/>
        ))}
        {fillPath && <path d={fillPath} fill="url(#chartFill)"/>}
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
        {/* Marcador no último ponto do produto */}
        {productPath && (
          <>
            <circle cx={toX(lastPt.t)} cy={toY(lastPt.v)} r="4" fill={productSeries.color}/>
            <circle cx={toX(lastPt.t)} cy={toY(lastPt.v)} r="9" fill={productSeries.color} opacity="0.18"/>
          </>
        )}
        <text x={PADX} y={14} fill="rgba(255,255,255,0.5)" fontSize="10" fontFamily="JetBrains Mono">
          {'R$ ' + vMax.toFixed(2).replace('.', ',')}
        </text>
        <text x={PADX} y={H - 6} fill="rgba(255,255,255,0.5)" fontSize="10" fontFamily="JetBrains Mono">
          {'R$ ' + vMin.toFixed(2).replace('.', ',')}
        </text>
      </svg>
      {activeSeries.filter(s => s.data.length >= 2).length > 1 && (
        <div style={{display:'flex', gap: 14, marginTop: 6, flexWrap:'wrap'}}>
          {activeSeries.filter(s => s.data.length >= 2).map(s => (
            <div key={s.id} style={{display:'flex', alignItems:'center', gap: 5, fontSize: 11, color:'var(--ma-fg-muted)'}}>
              <span style={{width: 10, height: 2, background: s.color, display:'inline-block', borderRadius: 1, opacity: 0.9}}/>
              {s.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

Object.assign(window, { PriceChart });
