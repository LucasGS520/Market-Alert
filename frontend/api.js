// Market Alert — API client
// Replaces the static window.MA_DATA from the prototype.
// All fetch calls go to /api/v1 (proxied by nginx to the FastAPI backend).

const API = '/api/v1';

// ── Helpers ──────────────────────────────────────────────────────────────────

function inferMarketplace(url) {
  if (!url) return null;
  if (url.includes('mercadolivre') || url.includes('mercadolibre')) return 'mercadolivre';
  if (url.includes('shopee')) return 'shopee';
  if (url.includes('magazineluiza') || url.includes('magalu')) return 'magalu';
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

// ── Product mapping ───────────────────────────────────────────────────────────

function mapProduct(p) {
  const mp = inferMarketplace(p.url_normalized || p.url_original);
  return {
    id: p.id,
    name: p.name || 'Produto sem nome',
    marketplace: mp,
    url_original: p.url_original,
    url_normalized: p.url_normalized,
    status: p.status,
    is_available: p.is_available,
    current_price: p.current_price != null ? Number(p.current_price) : null,
    previous_price: null,
    variation_24h: null,
    stability_level: null,
    check_interval_minutes: p.check_interval_minutes,
    next_check_at: relativeTime(p.next_check_at),
    next_check_reason: p.next_check_reason,
    last_checked_at: relativeTime(p.last_checked_at),
    consecutive_failures: p.consecutive_failures,
    icon: inferIcon(p.name),
    history: [],
    latest_comparison: p.latest_comparison ? mapComparison(p.latest_comparison) : null,
    competitors: [],
    competitors_count: p.competitors_count ?? 0,
  };
}

function mapComparison(c) {
  if (!c) return null;
  return {
    id: c.id,
    status: c.status,
    ranking: c.ranking,
    average_price: Number(c.average_price),
    min_price: Number(c.min_price),
    max_price: Number(c.max_price),
    potential_adjustment: c.potential_adjustment != null ? Number(c.potential_adjustment) : null,
    run_status: c.run_status,
    participants_count: c.participants_count,
    valid_competitors_count: c.valid_competitors_count,
    ignored_competitors_count: c.ignored_competitors_count,
  };
}

function mapCompetitor(c) {
  return {
    id: c.id,
    name: c.name || 'Concorrente',
    marketplace: inferMarketplace(c.url_normalized || c.url_original),
    url_original: c.url_original,
    url_normalized: c.url_normalized,
    current_price: c.current_price != null ? Number(c.current_price) : null,
    variation_24h: null,
    last_checked_at: relativeTime(c.last_checked_at),
    status: c.status,
    is_available: c.is_available,
  };
}

function mapNotification(n) {
  const meta = {
    urgent: ['price_rise', 'ranking_change', 'market_price_rise'],
  };
  return {
    id: n.id,
    monitored_id: n.monitored_id,
    event_type: n.event_type,
    delivery_status: n.delivery_status,
    title: n.title,
    message: n.message,
    error_message: n.error_message,
    run_status: n.run_status,
    participants_count: n.participants_count,
    sent_at: relativeTime(n.sent_at),
    kind: meta.urgent.includes(n.event_type) ? 'urgent' : 'info',
  };
}

// ── Enrich products with price history ───────────────────────────────────────

async function enrichWithHistory(product) {
  try {
    const r = await fetch(`${API}/price-history/${product.id}`);
    if (!r.ok) return product;
    const history = await r.json();
    if (!history || history.length === 0) return product;

    const prices = history
      .filter(h => h.price != null)
      .map(h => ({ price: Number(h.price), ts: new Date(h.collected_at || h.created_at).getTime() }))
      .sort((a, b) => a.ts - b.ts);

    if (prices.length === 0) return product;

    const now = Date.now();
    const cutoff24h = now - 86400000;
    const recent = prices.filter(h => h.ts >= cutoff24h);
    const current = prices[prices.length - 1]?.price ?? null;
    const prev24h = recent.length > 1 ? recent[0].price : (prices.length > 1 ? prices[prices.length - 2]?.price : null);

    const variation24h = (current != null && prev24h != null && prev24h !== 0)
      ? ((current - prev24h) / prev24h) * 100
      : null;

    const latestThumb = [...history].reverse().find(h => h.thumbnail_url);

    return {
      ...product,
      current_price: current ?? product.current_price,
      previous_price: prev24h,
      variation_24h: variation24h,
      history: prices.slice(-30).map(h => h.price),
      thumbnail_url: latestThumb ? latestThumb.thumbnail_url : (product.thumbnail_url ?? null),
    };
  } catch {
    return product;
  }
}

// ── API surface ───────────────────────────────────────────────────────────────

const MA_API = {
  async loadDashboard() {
    const [productsRaw, notificationsRaw] = await Promise.all([
      fetch(`${API}/monitored/`).then(r => r.json()).catch(() => []),
      fetch(`${API}/notifications?limit=50`).then(r => r.json()).catch(() => []),
    ]);

    const products = await Promise.all(
      (Array.isArray(productsRaw) ? productsRaw : [])
        .map(p => enrichWithHistory(mapProduct(p)))
    );

    const notifications = (Array.isArray(notificationsRaw) ? notificationsRaw : [])
      .map(mapNotification);

    return { products, notifications };
  },

  async loadProductDetail(productId) {
    const [detailRaw, competitorsRaw] = await Promise.all([
      fetch(`${API}/monitored/${productId}`).then(r => r.json()).catch(() => null),
      fetch(`${API}/monitored/${productId}/competitors`).then(r => r.json()).catch(() => []),
    ]);

    if (!detailRaw) return null;

    let product = mapProduct(detailRaw);
    product = await enrichWithHistory(product);

    const competitors = (Array.isArray(competitorsRaw) ? competitorsRaw : [])
      .map(mapCompetitor);

    const competitorCount = competitors.length;

    // Enrich each competitor with its price history for variation_24h
    const enrichedCompetitors = await Promise.all(
      competitors.map(async c => {
        try {
          const r = await fetch(`${API}/price-history/competitor/${c.id}`);
          if (!r.ok) return c;
          const h = await r.json();
          if (!h || h.length === 0) return c;
          const prices = h
            .filter(x => x.price != null)
            .map(x => ({ price: Number(x.price), ts: new Date(x.collected_at || x.created_at).getTime() }))
            .sort((a, b) => a.ts - b.ts);
          if (prices.length < 2) return c;
          const now = Date.now();
          const cutoff = now - 86400000;
          const recent = prices.filter(x => x.ts >= cutoff);
          const cur = prices[prices.length - 1]?.price;
          const prev = recent.length > 1 ? recent[0].price : prices[prices.length - 2]?.price;
          const variation = (cur != null && prev != null && prev !== 0)
            ? ((cur - prev) / prev) * 100 : null;
          const latestThumb = [...h].reverse().find(x => x.thumbnail_url);
          return {
            ...c,
            current_price: cur ?? c.current_price,
            variation_24h: variation,
            thumbnail_url: latestThumb ? latestThumb.thumbnail_url : (c.thumbnail_url ?? null),
          };
        } catch {
          return c;
        }
      })
    );

    return {
      ...product,
      competitors: enrichedCompetitors,
      competitors_count: competitorCount,
    };
  },
};

window.MA_API = MA_API;
