# Classificacao de Campos por Origem e Uso

Versao: 1.0

Todo campo do dominio pertence a uma de tres classes. Misturar classes dentro de uma camada e o principal vetor de acoplamento entre produto monitorado e mercado.

## Classes

- **Observado**: fato coletado diretamente do marketplace. Imutavel apos persistido.
- **Derivado**: calculado a partir de dados observados. Pode ser recalculado sem perda de fato.
- **Decisorio**: campo ou regra que direciona comportamento operacional (agendamento, notificacao, comparacao). Deve derivar do mercado consolidado, nao do estado interno do produto.

---

## MonitoredProduct

| Campo | Classe | Origem | Usado por |
|---|---|---|---|
| `id`, `url_original`, `url_normalized` | Observado | Cadastro do usuario | Identidade, navegacao |
| `name` | Observado | Scraper (ou usuario) | Exibicao, contexto |
| `current_price` | Observado | Scraper | Snapshot de mercado, sinal de preco |
| `is_available` | Observado | Scraper | Eligibilidade da oferta de referencia |
| `status` | Derivado | Resultado da coleta | Ciclo de vida, elegibilidade estrutural |
| `last_checked_at`, `last_successful_collection_at` | Observado | Coleta | Diagnostico, UI |
| `consecutive_failures` | Derivado | Resultado da coleta | Diagnostico |
| `stability_level` | Derivado | `policy.classify_stability` | Exibicao (nao deve governar agendamento diretamente) |
| `next_check_at`, `check_interval_minutes` | Decisorio | `policy.compute_next_check` via scheduler | Agendamento |
| `next_check_reason` | Decisorio | Scheduler | Diagnostico de agendamento |
| `last_price_changed_at` | Derivado | Coleta (detecta mudanca) | Input para `classify_stability` |
| `last_availability_changed_at` | Derivado | Coleta (detecta mudanca) | Input para `classify_stability` |
| `last_market_changed_at` | Derivado | `comparison_task` (snapshot elegivel) | Input para `classify_stability` — sinal de mercado |
| `collection_lease_until` | Decisorio | Scheduler / orchestrator | Coordenacao de coleta (Redis e backup) |

---

## Competitor

| Campo | Classe | Origem | Usado por |
|---|---|---|---|
| `id`, `url_original`, `url_normalized` | Observado | Cadastro do usuario | Identidade |
| `name` | Observado | Scraper | Exibicao |
| `current_price` | Observado | Scraper | Formacao do mercado |
| `is_available` | Observado | Scraper | Elegibilidade no snapshot |
| `status` | Derivado | Resultado da coleta | Elegibilidade no snapshot |

---

## Comparison (snapshot de mercado)

### Dados de mercado — sempre presentes quando ha ofertas validas

| Campo | Classe | Origem | Usado por |
|---|---|---|---|
| `min_price`, `max_price`, `average_price` | Derivado | `comparison_service` | UI, sinais de mercado |
| `participants_count` | Derivado | `comparison_service` | Auditoria, UI |
| `valid_competitors_count`, `ignored_competitors_count` | Derivado | `comparison_service` | Auditoria, quorum |
| `run_status` | Decisorio | `collection_run` + `comparison_service` | Elegibilidade de notificacao |
| `reference_available` | Decisorio | `comparison_service` | Condiciona exibicao de posicao da referencia |

### Dados da oferta de referencia — condicionais (`reference_available == True`)

| Campo | Classe | Origem | Usado por |
|---|---|---|---|
| `status` | Derivado | `_calcular_status` | Badge de posicao competitiva |
| `ranking` | Derivado | `comparison_service` | Exibicao de posicao |
| `potential_adjustment` | Derivado | `comparison_service` | Sugestao de ajuste de preco |
| `product_price` | Observado | Preco da referencia no momento | Auditoria |

---

## PriceHistory

| Campo | Classe | Origem | Usado por |
|---|---|---|---|
| `price` | Observado | Scraper | Indicadores temporais, sparkline |
| `is_available` | Observado | Scraper | Filtro de precos validos |
| `collected_at` | Observado | Coleta | Janelas temporais (24h, total) |
| `thumbnail_url` | Observado | Scraper | Exibicao de concorrente |

---

## Indicadores derivados (nao persistidos — calculados por `market_indicators_service`)

| Campo | Classe | Origem | Usado por |
|---|---|---|---|
| `variation_24h` (referencia) | Derivado | `PriceHistory` da referencia | UI — badge de variacao do produto |
| `variation_all` | Derivado | `PriceHistory` da referencia | UI — variacao historica total |
| `previous_price` | Derivado | `PriceHistory` da referencia | UI — preco anterior |
| `sparkline` | Derivado | `PriceHistory` da referencia | UI — grafico de linha |
| `market_variation_24h` | Derivado | `Comparison.min_price` (24h) | UI — variacao do mercado |
| `variation_24h` (concorrente) | Derivado | `PriceHistory` do concorrente | UI — badge do concorrente |

---

## Regra de nao-invasao

Uma camada nao deve usar campos de outra classe sem justificativa explicita:

- Campos **observados** nao devem governar logica de decisao diretamente (ex.: `current_price` nao decide agendamento — quem decide e a estabilidade de mercado).
- Campos **derivados** de produto nao devem substituir dados do snapshot de mercado (ex.: `stability_level` do produto e para exibicao; quem governa o delay e `policy.compute_next_check` com o estado do mercado).
- Campos **decisorios** nao devem ser recalculados fora das camadas designadas (ex.: `next_check_at` so deve ser escrito pelo scheduler service).
