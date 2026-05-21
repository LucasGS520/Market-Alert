// Formatadores e inferencias compartilhados pela UI estatica.
// Carrega antes de mappers/client para expor helpers no escopo global do navegador.

const API = '/api/v1';

function inferMarketplace(url) {
  // Suporte oficial do frontend: apenas Mercado Livre ate existir adapter validado.
  if (!url) return null;
  if (url.includes('mercadolivre') || url.includes('mercadolibre')) return 'mercadolivre';
  return null;
}

function inferIcon(name) {
  if (!name) return 'package';
  const lower = name.toLowerCase();
  if (lower.includes('relógio') || lower.includes('relogio') || lower.includes('watch')) return 'clock';
  if (lower.includes('celular') || lower.includes('iphone') || lower.includes('samsung')) return 'zap';
  if (lower.includes('tênis') || lower.includes('tenis') || lower.includes('sapato') || lower.includes('shoe')) return 'package';
  return 'package';
}

function relativeTime(isoString) {
  // Mantem datas de API legiveis na interface sem alterar o valor persistido.
  if (!isoString) return null;
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return isoString;
  const now = Date.now();
  const diff = now - date.getTime();
  if (diff < 0) {
    const future = -diff;
    if (future < 60000) return 'em menos de 1 min';
    if (future < 3600000) return `em ${Math.round(future / 60000)} min`;
    if (future < 86400000) return `em ${Math.round(future / 3600000)}h`;
    return date.toLocaleDateString('pt-BR');
  }
  if (diff < 60000) return 'agora';
  if (diff < 3600000) return `há ${Math.round(diff / 60000)} min`;
  if (diff < 86400000) return `há ${Math.round(diff / 3600000)}h`;
  if (diff < 172800000) return 'ontem';
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

function brl(n) {
  if (n == null || isNaN(n)) return 'R$ —';
  return 'R$ ' + Number(n).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// A UI nao usa modulos ESM; estes nomes formam o contrato global consumido pelos JSX.
Object.assign(window, { API, inferMarketplace, inferIcon, relativeTime, brl });
