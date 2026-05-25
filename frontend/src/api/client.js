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
        variation_24h: p.variation_24h ?? null,
        variation_all: p.variation_all ?? null,
        previous_price: p.previous_price != null ? Number(p.previous_price) : null,
        history: Array.isArray(p.sparkline) ? p.sparkline : [],
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

    const mapped = mapProduct(detailRaw);
    const product = {
      ...mapped,
      variation_24h: detailRaw.variation_24h ?? null,
      variation_all: detailRaw.variation_all ?? null,
      previous_price: detailRaw.previous_price != null ? Number(detailRaw.previous_price) : null,
      history: Array.isArray(detailRaw.sparkline) ? detailRaw.sparkline : [],
    };

    // Resumo dos concorrentes (variation_24h, thumbnail_url) já calculado pelo backend
    const summaryMap = {};
    const backendCompetitors = detailRaw.latest_comparison?.competitors;
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
        variation_24h: summary.variation_24h ?? null,
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
