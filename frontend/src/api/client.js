/* global API, mapProduct, mapCompetitor, mapNotification */
// Cliente HTTP do frontend. Consolida as chamadas que as telas precisam consumir.

async function enrichWithHistory(product) {
  // Enriquecimento client-side: historico alimenta metricas visuais, nao regras duraveis.
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

    // Variação de 24h e sparklines sao derivadas para exibicao no dashboard/detalhe.
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
    // Falha em endpoint auxiliar nao deve bloquear a navegacao principal.
    return product;
  }
}

const MA_API = {
  async loadDashboard() {
    // Dashboard monta a tela no cliente com chamadas paralelas, sem agregador backend unico.
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
    // Detalhe combina produto e concorrentes; historicos sao buscados depois para graficos.
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
          // Concorrente sem historico continua aparecendo com os dados principais.
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

// Contrato publico do frontend para App.jsx.
Object.assign(window, { MA_API, enrichWithHistory });
