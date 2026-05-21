/* global React */
// Wrapper visual minimo para paineis e listas; nao deve conter regra de tela.

function Card({ children, raised, glow, padded = true, style, className = '' }) {
  const cls = ['ma-card', raised ? 'is-raised' : '', glow ? 'is-glow' : '', padded ? 'is-padded' : '', className].join(' ');
  return <div className={cls} style={style}>{children}</div>;
}

Object.assign(window, { Card });
