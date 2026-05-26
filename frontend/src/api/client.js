/* global API, mapProduct, mapCompetitor, mapNotification */
// Cliente HTTP do frontend. Consolida as chamadas que as telas precisam consumir.
// Indicadores de variação (variation_24h, variation_all, sparkline) são fornecidos
// pelo backend — não são recalculados aqui.

const MA_API = {
  async loadDashboard() {
    const [productsRaw, notificationsRaw] = await Promise.all([
      fetch(`${API}/monitored/`).then(r => r.json()).catch(() => []),
      fetch(`${API}/notifications?limit=50`).then(r => r.json()).catch(() => []),
    ]);

    const products = (Array.isArray(productsRaw) ? productsRaw : []).map(p => {
      const mapped = mapProduct(p);
      return {
        ...mapped,
        thumbnail_url: p.thumbnail_url ?? null,
        variation_24h: p.variation_24h ?? null,
        variation_all: p.variation_all ?? null,
        previous_price: p.previous_price != null ? Number(p.previous_price) : null,
        history: Array.isArray(p.sparkline) ? p.sparkline : [],
        market_avg_sparkline: Array.isArray(p.market_avg_sparkline) ? p.market_avg_sparkline : [],
        // substitui last_history_ts que antes vinha do enriquecimento com price-history
        last_history_ts: mapped.last_successful_collection_at_raw
          ? new Date(mapped.last_successful_collection_at_raw).getTime()
          : null,
      };
    });

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

    const cmpRaw = detailRaw.latest_comparison;
    const mapped = mapProduct(detailRaw);
    const product = {
      ...mapped,
      // Indicadores do produto "desde o início"
      initial_price: detailRaw.initial_price != null ? Number(detailRaw.initial_price) : null,
      previous_price: detailRaw.previous_price != null ? Number(detailRaw.previous_price) : null,
      variation_since_start: detailRaw.variation_since_start ?? null,
      variation_since_previous: detailRaw.variation_since_previous ?? null,
      trend_since_start: detailRaw.trend_since_start ?? 'insufficient_data',
      product_series: Array.isArray(detailRaw.product_series) ? detailRaw.product_series : [],
      // Séries e indicadores de mercado (de latest_comparison)
      market_min_series: Array.isArray(cmpRaw?.market_min_series) ? cmpRaw.market_min_series : [],
      market_avg_series: Array.isArray(cmpRaw?.market_avg_series) ? cmpRaw.market_avg_series : [],
      market_min_current: cmpRaw?.market_min_current != null ? Number(cmpRaw.market_min_current) : null,
      market_min_variation_since_start: cmpRaw?.market_min_variation_since_start ?? null,
      market_avg_current: cmpRaw?.market_avg_current != null ? Number(cmpRaw.market_avg_current) : null,
      market_avg_variation_since_start: cmpRaw?.market_avg_variation_since_start ?? null,
    };

    // Resumo dos concorrentes (variation_since_start, gap, thumbnail) calculado pelo backend
    const summaryMap = {};
    const backendCompetitors = cmpRaw?.competitors;
    if (Array.isArray(backendCompetitors)) {
      for (const s of backendCompetitors) {
        summaryMap[s.id] = s;
      }
    }

    const competitors = (Array.isArray(competitorsRaw) ? competitorsRaw : []).map(c => {
      const base = mapCompetitor(c);
      const summary = summaryMap[c.id] || {};
      return {
        ...base,
        variation_since_start: summary.variation_since_start ?? null,
        initial_price: summary.initial_price != null ? Number(summary.initial_price) : null,
        gap_vs_product: summary.gap_vs_product != null ? Number(summary.gap_vs_product) : null,
        gap_vs_product_percent: summary.gap_vs_product_percent ?? null,
        thumbnail_url: summary.thumbnail_url ?? null,
      };
    });

    return {
      ...product,
      competitors,
      competitors_count: competitors.length,
    };
  },

  async search(q) {
    if (!q || q.trim().length < 2) return [];
    try {
      const r = await fetch(`${API}/monitored/search?q=${encodeURIComponent(q.trim())}`);
      if (!r.ok) return [];
      return r.json();
    } catch {
      return [];
    }
  },
};

// Contrato publico do frontend para App.jsx.
Object.assign(window, { MA_API });
