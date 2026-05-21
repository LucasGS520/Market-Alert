# Contrato Workers e Celery

Versao: 1.0  
Proprietario logico: `backend/market_alert/app/workers`  
Consumidores: API, scheduler, services de dominio e operadores.

## Filas

- `collection`: coleta de produto e concorrente. No Docker Compose usa concorrencia `1` e `prefetch-multiplier=1`.
- `comparison`: calculo de comparacoes.
- `notification`: entrega de notificacoes.
- `default`: fila geral usada junto da comparacao quando aplicavel.

## `collector_task`

Assinatura:

```python
collector_task(
    product_id: str | None = None,
    competitor_id: str | None = None,
    run_id: str | None = None,
)
```

Contrato:

- Recebe exatamente um entre `product_id` e `competitor_id`.
- `run_id` identifica rodada coordenada quando a coleta e de concorrente.
- Produto `paused` ou `unsupported` e ignorado.
- Concorrente em rodada marca estado no Redis como `done`, `failed`, `deferred` ou `skipped`.
- Coleta autonoma de concorrente pode disparar `comparison_task`.

## `comparison_task`

Assinatura:

```python
comparison_task(
    monitored_id: str,
    old_price: str | None = None,
    new_price: str | None = None,
    run_id: str | None = None,
)
```

Contrato:

- Com `run_id`, aguarda a rodada coordenada sair de `pending`.
- Calcula snapshot competitivo via service de comparacao.
- Pode persistir comparacao sem notificar quando a rodada esta degradada.
- Converte sinais tecnicos em no maximo um alerta publico.

## `notification_task`

Assinatura:

```python
notification_task(
    monitored_id: str,
    comparison_id: str | None,
    alert_type: str,
    old_price: str | None,
    new_price: str | None,
    old_status: str | None,
    new_status: str | None,
    product_url: str,
    product_name: str | None = None,
    old_ranking: int | None = None,
    new_ranking: int | None = None,
    market_min_old: str | None = None,
    market_min_new: str | None = None,
    reason_codes: list[str] | None = None,
    run_id: str | None = None,
    run_status: str | None = None,
    participants_count: int | None = None,
)
```

Contrato:

- Entrega via ntfy quando `ntfy_topic` esta configurado.
- Registra tentativa em `notification_logs`.
- Falhas retryable usam retry Celery.
- Cooldown e deduplicacao podem bloquear entrega sem falha.

## `scheduler_task`

Contrato:

- Executa pelo Celery Beat a cada minuto.
- Usa lock global Redis para evitar ciclos simultaneos.
- Delega selecao e lease ao scheduler service.
- Enfileira produtos elegiveis com `next_check_at <= now`.

## Estados de rodada em Redis

Chave: `collection_run:{run_id}`

Estados por concorrente:

- `pending`
- `done`
- `failed`
- `deferred`
- `skipped`

Estados finais:

- `complete`
- `partial`
- `expired`
- `no_competitors`

`partial`, `expired` e `no_competitors` permitem auditoria, mas bloqueiam notificacao competitiva.
