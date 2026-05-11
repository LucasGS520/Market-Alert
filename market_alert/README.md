# market_alert

`market_alert` e o modulo de negocio responsavel por monitorar URLs de produtos,
coletar precos via `market_scraper`, comparar o produto monitorado com seus
concorrentes e disparar notificacoes quando houver variacao relevante.

## Arquitetura atual

```text
FastAPI /api/v1
  -> services de dominio
    -> PostgreSQL via SQLAlchemy async
    -> Redis para locks, rate limit, cache e cooldown
    -> Celery para coleta, comparacao e agendamento
      -> market_scraper via HTTP
      -> ntfy / telert para notificacoes
```

O modulo esta organizado por fronteiras de dominio:

- `app/api/v1`: camada HTTP fina. Valida entrada, chama servicos e retorna schemas.
- `app/products`: agregado de produtos monitorados, concorrentes e historico de precos.
- `app/comparison`: calculo e persistencia de snapshots competitivos.
- `app/notifications`: deteccao de eventos, envio e log de notificacoes.
- `app/infra`: configuracao, banco e clientes externos.
- `app/workers`: Celery, scheduler, locks/cache Redis e tarefas assincronas.

## Fluxo principal

1. `POST /api/v1/monitored/scrape` cadastra um produto monitorado e enfileira
   `collector_task(product_id=...)`.
2. `collector_task` chama `market_scraper`, atualiza o produto, grava
   `price_history` e agenda a proxima coleta.
3. Quando a coleta e de um produto monitorado, a task tambem enfileira a coleta
   dos concorrentes e `comparison_task(monitored_id=...)`.
4. `comparison_task` recalcula ranking, preco medio/minimo/maximo e status
   competitivo.
5. Apos a comparacao, `notifications` avalia variacao de preco/status e envia
   alerta por `ntfy` e/ou `telert`, respeitando cooldown no Redis.
6. `scheduler_task`, executada pelo Celery Beat a cada minuto, enfileira produtos
   ativos com `next_check_at <= now`.

## Contratos atuais

API publica principal:

- `POST /api/v1/monitored/scrape`
- `GET /api/v1/monitored/`
- `GET /api/v1/monitored/{product_id}`
- `PATCH /api/v1/monitored/{product_id}/pause`
- `PATCH /api/v1/monitored/{product_id}/resume`
- `DELETE /api/v1/monitored/{product_id}`
- `POST /api/v1/competitors/scrape`
- `GET /api/v1/competitors/?monitored_id=...`
- `DELETE /api/v1/competitors/{competitor_id}`
- `GET /api/v1/comparisons/{monitored_id}`
- `GET /api/v1/comparisons/{monitored_id}/history`
- `GET /api/v1/price-history/{monitored_id}`
- `GET /api/v1/price-history/competitor/{competitor_id}`

Contrato com `market_scraper`:

- Request: `POST {SCRAPER_URL}/scraper/parse` com `{"url": "<produto>"}`.
- Sucesso `200`: retorna marketplace, preco, disponibilidade e metadados de coleta.
- Erro semantico `422`: retorna `error_code`, `marketplace`, `url`,
  `retryable` e `message`.
- Erros de conexao, timeout ou HTTP inesperado sao tratados como scraper
  indisponivel e podem ser retentados pelo worker.

Tasks internas:

- `collector_task(product_id=None, competitor_id=None)`: aceita exatamente um
  identificador e executa uma coleta.
- `comparison_task(monitored_id, old_price=None, new_price=None, old_status=None)`:
  recalcula comparacao e avalia notificacoes.
- `scheduler_task()`: consulta produtos ativos vencidos e enfileira coletas.

## Validacao operacional

Com as dependencias instaladas, a verificacao minima antes de refatorar e:

```powershell
cd market_alert
python -c "import app.main; import app.workers.tasks"
pytest
alembic upgrade head
```

Com Docker:

```powershell
docker compose up --build
```

Validar `http://localhost:8000/health`, `http://localhost:8000/docs`,
PostgreSQL, Redis, workers Celery e comunicacao com `market_scraper`.
