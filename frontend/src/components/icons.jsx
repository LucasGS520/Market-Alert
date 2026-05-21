/* global React */
// Biblioteca local de icones SVG. Mantida em paths porque a UI nao possui bundler.

const ICONS = {
  bell: 'M6 8a6 6 0 0112 0c0 7 3 9 3 9H3s3-2 3-9|M10.3 21a1.94 1.94 0 003.4 0',
  'trend-up': 'M22 17l-8.5-8.5-5 5L2 7|M16 17h6v-6',
  'trend-down': 'M22 7l-8.5 8.5-5-5L2 17|M16 7h6v6',
  link: 'M10 13a5 5 0 007 0l3-3a5 5 0 00-7-7l-1 1|M14 11a5 5 0 00-7 0l-3 3a5 5 0 007 7l1-1',
  globe: 'M12 22a10 10 0 100-20 10 10 0 000 20z|M2 12h20|M12 2a14 14 0 010 20|M12 2a14 14 0 000 20',
  refresh: 'M21 12a9 9 0 11-3-6.7L21 8|M21 3v5h-5',
  search: 'M11 18a7 7 0 100-14 7 7 0 000 14z|M21 21l-4.3-4.3',
  tag: 'M20.59 13.41L13.42 20.58a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z|M7 7h.01',
  zap: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  target: 'M12 22a10 10 0 100-20 10 10 0 000 20z|M12 18a6 6 0 100-12 6 6 0 000 12z|M12 14a2 2 0 100-4 2 2 0 000 4z',
  package: 'M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z|M3.27 6.96L12 12.01l8.73-5.05|M12 22.08V12',
  eye: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z|M12 15a3 3 0 100-6 3 3 0 000 6z',
  calendar: 'M19 4H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2z|M16 2v4|M8 2v4|M3 10h18',
  chart: 'M3 3v18h18|M7 14l4-4 4 4 5-5',
  home: 'M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z|M9 22V12h6v10',
  clock: 'M12 22a10 10 0 100-20 10 10 0 000 20z|M12 7v5l3 3',
  plus: 'M12 5v14|M5 12h14',
  x: 'M18 6L6 18|M6 6l12 12',
  more: 'M12 13a1 1 0 100-2 1 1 0 000 2z|M19 13a1 1 0 100-2 1 1 0 000 2z|M5 13a1 1 0 100-2 1 1 0 000 2z',
  check: 'M20 6L9 17l-5-5',
  'chevron-down': 'M6 9l6 6 6-6',
  'chevron-up': 'M18 15l-6-6-6 6',
  'chevron-right': 'M9 6l6 6-6 6',
  'chevron-left': 'M15 6l-6 6 6 6',
  'arrow-right': 'M5 12h14|M12 5l7 7-7 7',
  'arrow-up-right': 'M7 17L17 7|M7 7h10v10',
  external: 'M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6|M15 3h6v6|M10 14L21 3',
  filter: 'M22 3H2l8 9.5V19l4 2v-8.5z',
  settings: 'M12 15a3 3 0 100-6 3 3 0 000 6z|M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z',
  pause: 'M6 4h4v16H6z|M14 4h4v16h-4z',
  play: 'M5 3l14 9-14 9z',
  trash: 'M3 6h18|M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2|M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6',
  edit: 'M12 20h9|M16.5 3.5a2.121 2.121 0 113 3L7 19l-4 1 1-4z',
  download: 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4|M7 10l5 5 5-5|M12 15V3',
  webhook: 'M18 16.98h-5.99c-1.66 0-3.01-1.34-3.01-3s1.34-3 3.01-3H18|M11 5.97V7c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3M16 8.97V7c0-1.66-1.34-3-3-3s-3 1.34-3 3M4.99 11.97V19a2 2 0 002 2h12',
  inbox: 'M22 12h-6l-2 3h-4l-2-3H2|M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z',
  warning: 'M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z|M12 9v4|M12 17h.01',
  sparkles: 'M12 3l1.9 5.8L20 11l-5.8 1.9L12 19l-1.9-5.8L4 11l5.8-2.2z|M5 3v4|M19 17v4|M3 5h4|M17 19h4',
};

function Icon({ name, size = 16, color, style, className = '' }) {
  // Retorna null para nomes desconhecidos para evitar quebra visual em metadados novos.
  const def = ICONS[name];
  if (!def) return null;
  const paths = def.split('|');
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color || 'currentColor'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      style={style} className={`ma-icon ${className}`}>
      {paths.map((d, i) => <path key={i} d={d}/>)}
    </svg>
  );
}

// Icon fica global para todos os componentes carregados por script tags.
Object.assign(window, { ICONS, Icon });
