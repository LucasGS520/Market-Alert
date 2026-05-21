# Runbook Operacional

Versao: 1.0  
Ambiente oficial: Docker Compose local.

## Subir ambiente

```powershell
docker compose up --build
```

Validar servicos:

```powershell
docker compose ps
```

## Health checks

- API: `http://localhost:8000/health`
- Scraper vivo: `http://localhost:8001/live`
- Scraper pronto: `http://localhost:8001/ready`
- Frontend: `http://localhost:3000`

## Validar backend fora do Docker

Dentro de `market_alert/`:

```powershell
python -c "import app.main; import app.workers.tasks"
pytest
alembic upgrade head
```

## Diagnosticar coleta

1. Verificar produto em `GET /api/v1/monitored/{product_id}`.
2. Verificar health em `GET /api/v1/monitored/{product_id}/health`.
3. Conferir `status`, `next_check_at`, `next_check_reason` e `consecutive_failures`.
4. Conferir `recent_attempts` para `captcha`, `blocked`, `timeout`, `price_not_found`, `rate_limited` ou `domain_circuit_open`.
5. Confirmar que o scraper responde em `/live` e `/ready`.
6. Confirmar que o worker `collection` esta ativo.

## Diagnosticar comparacao

1. Confirmar que o produto principal tem `current_price` e `status=active`.
2. Confirmar concorrentes ativos, disponiveis e com preco maior que zero.
3. Consultar `GET /api/v1/comparisons/{monitored_id}`.
4. Se nao houver comparacao, verificar se a coleta terminou e se a rodada saiu de `pending`.
5. Rodadas `partial`, `expired` e `no_competitors` podem persistir comparacao, mas bloqueiam notificacao.

## Diagnosticar ausencia de notificacao

Verificar na ordem:

1. `NTFY_TOPIC` esta configurado?
2. Existe comparacao nova ou ela foi deduplicada?
3. `run_status` e `complete`?
4. `valid_competitors_count >= NOTIFICATION_MIN_QUORUM`?
5. A variacao atingiu `NOTIFICATION_DELTA_PERCENT`?
6. Houve sinal tecnico relevante: preco, status, ranking ou menor preco de mercado?
7. Cooldown esta ativo em Redis?
8. Ja existe entrega `sent` para a mesma comparacao e tipo?
9. A task `notification_task` executou na fila `notification`?
10. `GET /api/v1/notifications` mostra tentativa `failed` com erro de entrega?

## Diagnosticar scraper

1. `GET /live` deve retornar `{"status": "ok"}`.
2. `GET /ready` deve retornar browser `ready`.
3. URL fora de Mercado Livre deve retornar `422` com `MARKETPLACE_NOT_SUPPORTED`.
4. Timeout global retorna `504` com `TIMEOUT`.
5. Se o browser nao iniciou, verificar logs de `browser_startup_falhou`.

## Regras de manutencao operacional

- Nao limpar Redis durante coleta ativa sem aceitar perda de locks, cooldowns e rodadas.
- Nao apagar PostgreSQL se quiser preservar historico e auditoria.
- Alteracoes de contrato devem atualizar `docs/contracts`.
- Alteracoes de arquitetura devem criar ou atualizar ADR.
- Alteracoes de comportamento devem atualizar baseline, fluxo E2E e README do servico afetado.
