/* global React, Icon */
// Controles de acao reutilizaveis. A semantica visual vem das classes do ui-kit.

function Button({ kind = 'primary', size = 'md', leading, trailing, children, onClick, style, disabled }) {
  return (
    <button className={`ma-btn ma-btn-${kind} ma-btn-${size}`} onClick={onClick} style={style} disabled={disabled}>
      {leading && <Icon name={leading} size={size === 'sm' ? 12 : 14}/>}
      <span>{children}</span>
      {trailing && <Icon name={trailing} size={size === 'sm' ? 12 : 14}/>}
    </button>
  );
}

function IconButton({ name, onClick, active, size = 'md', title }) {
  return (
    <button
      className={`ma-iconbtn ${active ? 'is-active' : ''} ma-iconbtn-${size}`}
      onClick={onClick}
      title={title}
      aria-label={title}>
      <Icon name={name} size={size === 'sm' ? 14 : 16}/>
    </button>
  );
}

Object.assign(window, { Button, IconButton });
