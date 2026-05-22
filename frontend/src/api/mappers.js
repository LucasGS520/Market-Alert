/* global inferMarketplace, inferIcon, relativeTime */
// Mapping entre payloads da API e o modelo de tela.
// Nao carrega regra de negocio: apenas normaliza nomes, numeros e campos opcionais.

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
    stability_level: p.stability_level || null,
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
  // Comparison chega pronta do backend; o frontend so converte valores para exibicao.
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
  // Mantem a semantica do NotificationLog e adiciona apenas classificacao visual.
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

// Exposicao necessaria porque os arquivos sao carregados por script tags, sem imports.
Object.assign(window, { mapProduct, mapComparison, mapCompetitor, mapNotification });
