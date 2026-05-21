# market_alert

Este README descreve o backend principal. A governanca oficial de arquitetura,
contratos, decisoes e operacao fica no [README raiz](../README.md).

`market_alert` é o módulo de negócio responsável por monitorar URLs de produtos,
coletar preços via `market_scraper`, comparar o produto monitorado com seus
concorrentes e disparar notificações quando houver variação relevante.

## Arquitetura

```text
FastAPI /api/v1
  -> services de domínio
    -> PostgreSQL via SQLAlchemy async
    -> Redis (DB 0) — locks, rate limit, cooldowns, rodadas coordenadas
    -> Celery (broker DB 1, results DB 2) — coleta, comparação, agendamento
      -> market_scraper via HTTP
      -> ntfy / telert para notificações
```

Organização por fronteiras de domínio:

- `app/api/v1`: camada HTTP fina — valida entrada, chama serviços, retorna schemas
- `app/products`: produtos monitorados, concorrentes e histórico de preços
- `app/comparison`: cálculo e persistência de snapshots competitivos
- `app/notifications`: detecção de eventos, envio e log de notificações
- `app/infra`: configuração, banco, clientes externos e classificação de erros
- `app/workers`: Celery, scheduler, tasks, locks/cache Redis, rodadas coordenadas

---

## Fluxo principal

```
POST /api/v1/monitored/  (status=pending, next_check_at=now)
  ↓
collector_task(product_id)
  ↓
collect_product  →  market_scraper  →  PriceHistory + status=active
  ↓
rodada coordenada criada (collection_run:{product_id})
  ↓
collector_task(competitor_id, run_id=product_id)  ×N
  ↓
comparison_task(run_id=product_id)  — aguarda rodada concluir
  ↓
calculate_comparison  →  snapshot competitivo
  ↓
evaluate_and_send  →  ntfy / telert (se delta >= threshold e fora do cooldown)
```

O `scheduler_task` dispara a cada minuto pelo Celery Beat e reenfileira
`collector_task(product_id)` para cada produto elegível com `next_check_at <= now`.

---

## Operação de Coleta

No Docker Compose, a coleta roda em modo conservador: o worker da fila
`collection` usa concorrência 1 e `prefetch-multiplier=1`. Isso evita rajadas
de Playwright contra o mesmo marketplace e prioriza concluir coletas lentas com
respostas operacionais claras.

### Estados operacionais

| Status        | Significado                                   | Elegível para coleta?            |
|---------------|-----------------------------------------------|----------------------------------|
| `pending`     | Cadastrado, aguardando primeira coleta        | Sim                              |
| `active`      | Última coleta bem-sucedida                    | Sim                              |
| `unavailable` | Produto reconhecido, mas indisponível         | Sim (continua sendo monitorado)  |
| `error`       | Última coleta falhou com erro recuperável     | Sim (via `next_check_at`)        |
| `paused`      | Suspenso manualmente                          | Não                              |
| `unsupported` | Marketplace não suportado ou URL inválida     | Não                              |

### Tipos de coleta

| Tipo             | Gatilho                               | Escopo                              |
|------------------|---------------------------------------|-------------------------------------|
| Inicial          | `POST /api/v1/monitored/`             | Produto principal                   |
| Recorrente       | `scheduler_task` (Beat, 1 min)        | Produto + concorrentes elegíveis    |
| Concorrente novo | `POST /api/v1/monitored/{id}/competitors` | Concorrente individualmente     |
| Recuperação      | Retry Celery / próximo ciclo Beat     | Item que falhou anteriormente       |

### Rodada coordenada

Quando um produto monitorado é coletado com sucesso e possui concorrentes
elegíveis, o sistema cria uma **rodada coordenada** em Redis:

```
collection_run:{product_id}  →  Hash { competitor_id: "pending" | "done" }
TTL: COLLECTION_RUN_TIMEOUT_SECONDS (padrão 300 s)
```

Cada `collector_task(competitor_id, run_id=...)` marca sua conclusão via
`mark_done`. A `comparison_task` espera que todos os concorrentes estejam
`"done"` (retenta a cada 15 s) antes de calcular o snapshot competitivo.
Se o TTL expirar antes de todos terminarem, a comparação prossegue com os
dados disponíveis — garantia de progresso mesmo com falhas parciais.

### Agendamento adaptativo

O intervalo entre coletas (`check_interval_minutes`) se ajusta automaticamente:

| Condição                               | Novo intervalo                                       |
|----------------------------------------|------------------------------------------------------|
| Preço mudou                            | `max(MIN, atual // 2)` — aumenta frequência          |
| Preço estável por N tentativas         | `min(MAX, atual × 2)` — reduz frequência             |
| Demais                                 | Mantém intervalo atual                               |

`next_check_at` aplica jitter sobre o intervalo para evitar
thundering herd entre produtos com intervalos similares.

Parâmetros relevantes: `MIN_CHECK_INTERVAL_MINUTES`, `MAX_CHECK_INTERVAL_MINUTES`,
`CONSECUTIVE_UNCHANGED_THRESHOLD`.

### Classificação de erros do scraper

Todos os erros do `market_scraper` passam por `classify_scraper_error`
em `app/infra/scraper_errors.py`:

| `error_code`              | Status resultante | Ação                  | Domain cooldown? |
|---------------------------|-------------------|-----------------------|------------------|
| `CAPTCHA_DETECTED`        | `error`           | `retry_with_backoff`  | Sim              |
| `BLOCKED`                 | `error`           | `retry_with_backoff`  | Sim              |
| `TIMEOUT`                 | `error`           | `retry_with_backoff`  | Não              |
| `PRICE_NOT_FOUND`         | `error`           | `retry_later`         | Não              |
| `LAYOUT_CHANGED`          | `error`           | `retry_later`         | Não              |
| `REDIRECT_TO_SEARCH`      | `error`           | `no_retry`            | Não              |
| `UNAVAILABLE`             | `unavailable`     | `retry_later`         | Não              |
| `MARKETPLACE_NOT_SUPPORTED` | `unsupported`   | `no_retry`            | Não              |

Para erros com `domain_cooldown=True`, o domínio fica bloqueado por
`DOMAIN_CAPTCHA_COOLDOWN_SECONDS` antes da próxima tentativa.

Para erros com status `error`, o `next_check_at` recebe um backoff de
`COLLECTION_RETRY_BASE_DELAY_MINUTES × tentativa` (cap em
`COLLECTION_RETRY_MAX_DELAY_MINUTES`), servindo de fallback caso todos
os retries Celery se esgotem.

---

## Contratos

### API pública

| Método | Endpoint                                      | Descrição                            |
|--------|-----------------------------------------------|--------------------------------------|
| POST   | `/api/v1/monitored/`                          | Cadastrar produto monitorado         |
| GET    | `/api/v1/monitored/`                          | Listar produtos                      |
| GET    | `/api/v1/monitored/{id}`                      | Detalhe + última comparação          |
| PATCH  | `/api/v1/monitored/{id}/pause`                | Pausar monitoramento                 |
| PATCH  | `/api/v1/monitored/{id}/resume`               | Retomar monitoramento                |
| DELETE | `/api/v1/monitored/{id}`                      | Remover produto                      |
| POST   | `/api/v1/monitored/{id}/competitors`          | Adicionar concorrente                |
| GET    | `/api/v1/monitored/{id}/competitors`          | Listar concorrentes                  |
| DELETE | `/api/v1/competitors/{id}`                    | Remover concorrente                  |
| GET    | `/api/v1/comparisons/{id}`                    | Última comparação                    |
| GET    | `/api/v1/comparisons/{id}/history`            | Histórico de comparações             |
| GET    | `/api/v1/price-history/{id}`                  | Histórico de preços (produto)        |
| GET    | `/api/v1/price-history/competitor/{id}`       | Histórico de preços (concorrente)    |

### Contrato com `market_scraper`

- Request: `POST {SCRAPER_URL}/scraper/parse` com `{"url": "<produto>"}`.
- Sucesso `200`: retorna `marketplace`, `price`, `available`, `title`, `collected_at` e metadados.
- Erro semântico `422`: retorna `error_code`, `marketplace`, `url`, `retryable` e `message`.
- Timeout global `504`: retorna o mesmo payload estruturado com `error_code=TIMEOUT` e é tratado como retryable.
- Conexão recusada / timeout HTTP do cliente / HTTP inesperado → `ScraperUnavailableError` → retry automático.

### Tasks Celery internas

```python
collector_task(
    product_id: str | None = None,
    competitor_id: str | None = None,
    run_id: str | None = None,      # product_id da rodada, se parte de coleta coordenada
)

comparison_task(
    monitored_id: str,
    old_price: str | None = None,   # Decimal serializado, para avaliação de notificação
    new_price: str | None = None,
    run_id: str | None = None,      # aguarda rodada coordenada antes de calcular
)

scheduler_task()                    # dispara pelo Beat a cada 1 minuto
```

---

## Parâmetros de configuração relevantes (`.env`)

| Variável                              | Padrão | Descrição                                               |
|---------------------------------------|--------|---------------------------------------------------------|
| `MIN_CHECK_INTERVAL_MINUTES`          | `30`   | Intervalo mínimo entre coletas (minutos)                |
| `MAX_CHECK_INTERVAL_MINUTES`          | `240`  | Intervalo máximo entre coletas (minutos)                |
| `CONSECUTIVE_UNCHANGED_THRESHOLD`     | `3`    | Coletas sem variação para ampliar intervalo             |
| `COLLECTION_RETRY_BASE_DELAY_MINUTES` | `5`    | Base de backoff após erro (multiplicado pela tentativa) |
| `COLLECTION_RETRY_MAX_DELAY_MINUTES`  | `60`   | Cap máximo do backoff (minutos)                         |
| `COLLECTION_RUN_TIMEOUT_SECONDS`      | `300`  | SLA máximo de uma rodada coordenada (segundos)          |
| `DOMAIN_CAPTCHA_COOLDOWN_SECONDS`     | `300`  | Cooldown de domínio após CAPTCHA ou bloqueio            |
| `DOMAIN_RATE_LIMIT_TTL_SECONDS`       | `2`    | Cooldown curto entre coletas do mesmo domínio           |
| `SCRAPER_TIMEOUT_SECONDS`             | `270`  | Timeout do cliente `market_alert` ao chamar o scraper   |
| `MAX_TOTAL_REQUEST_SECONDS`           | `240`  | Timeout global por parse dentro do `backend/market_scraper`     |
| `PLAYWRIGHT_TIMEOUT_MS`               | `60000`| Timeout de navegação/espera do Playwright               |
| `NOTIFICATION_DELTA_PERCENT`          | `5.0`  | Variação mínima (%) para disparar alerta                |
| `NOTIFICATION_COOLDOWN_MINUTES`       | `30`   | Cooldown entre alertas do mesmo produto                 |
