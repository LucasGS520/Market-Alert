/* global React, Icon */
// Grafico principal do detalhe do produto; recebe serie ja enriquecida pelo client.
function PriceChart({ data, height = 220 }) {
  if (!data || data.length < 2) {
    return (
      <div style={{height, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--ma-fg-subtle)', fontSize: 12, gap: 8}}>
        <Icon name="warning" size={14}/>
        Sem histÃ³rico de preÃ§os ainda.
      </div>
    );
  }
  const W = 720, H = height, PADX = 12, PADY = 24;
  const min = Math.min(...data), max = Math.max(...data);
  // Expande a escala para evitar linha colada nas bordas do SVG.
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

Object.assign(window, { PriceChart });
