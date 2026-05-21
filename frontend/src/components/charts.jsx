/* global React */
// Graficos pequenos e independentes usados como indicacao visual de tendencia.

function Sparkline({ data, color = '#FF7A1A', width = 90, height = 24 }) {
  if (!data || data.length < 2) {
    return <span style={{display:'inline-block', width, height, background:'var(--ma-neutral-500)', borderRadius: 4, opacity: 0.4}}/>;
  }
  const min = Math.min(...data), max = Math.max(...data);
  // Normaliza a serie para caber no viewBox sem alterar os valores originais.
  const range = max - min || 1;
  const step = width / (data.length - 1);
  const pts = data.map((v, i) => [i * step, height - 2 - ((v - min) / range) * (height - 4)]);
  const d = 'M ' + pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' L ');
  const last = pts[pts.length-1];
  return (
    <svg className="ma-spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx={last[0]} cy={last[1]} r="2" fill={color}/>
    </svg>
  );
}

Object.assign(window, { Sparkline });
