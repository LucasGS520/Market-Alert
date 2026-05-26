# Contrato API v1

Versao: 1.0  
Proprietario logico: `backend/market_alert/app/api/v1`  
Consumidores: frontend, operadores via Swagger/OpenAPI, scripts locais.

## Regras gerais

- Prefixo oficial: `/api/v1`.
- A API deve permanecer fina: valida entrada, chama services e retorna schemas.
- Operacoes que disparam coleta retornam `202 Accepted` quando persistem e enfileiram ou tentam enfileirar trabalho assincrono.
- Remocoes retornam `204 No Content`.
- Erros de URL invalida retornam `400` com `detail.error = invalid_url`.
- Recursos inexistentes ou ainda sem dado calculado podem retornar `404`.

## Endpoints publicos

| Metodo | Endpoint | Status esperado | Uso |
|---|---|---:|---|
| POST | `/api/v1/monitored/` | 202 | Cadastrar produto monitorado e agendar primeira coleta |
| GET | `/api/v1/monitored/` | 200 | Listar produtos com resumo de comparacao |
| GET | `/api/v1/monitored/{product_id}` | 200/404 | Detalhar produto e ultima comparacao |
| PATCH | `/api/v1/monitored/{product_id}/pause` | 200/404 | Pausar monitoramento |
| PATCH | `/api/v1/monitored/{product_id}/resume` | 200/404 | Retomar monitoramento e tentar coleta |
| DELETE | `/api/v1/monitored/{product_id}` | 204/404 | Remover produto |
| GET | `/api/v1/monitored/{product_id}/health` | 200/404 | Diagnosticar coleta do produto |
| POST | `/api/v1/monitored/{monitored_id}/competitors` | 202 | Adicionar concorrente e tentar coleta |
| GET | `/api/v1/monitored/{monitored_id}/competitors` | 200 | Listar concorrentes |
| DELETE | `/api/v1/competitors/{competitor_id}` | 204/404 | Remover concorrente e tentar recalculo |
| GET | `/api/v1/comparisons/{monitored_id}` | 200/404 | Ler ultima comparacao |
| GET | `/api/v1/comparisons/{monitored_id}/history` | 200 | Ler historico de comparacoes |
| GET | `/api/v1/price-history/{monitored_id}` | 200 | Ler historico do produto |
| GET | `/api/v1/price-history/competitor/{competitor_id}` | 200 | Ler historico do concorrente |
| GET | `/api/v1/notifications` | 200 | Listar tentativas de notificacao |
| GET | `/api/v1/notifications/{notification_id}` | 200/404 | Detalhar tentativa de notificacao |

## Payload de criacao assincrona

Operacoes `POST` de produto e concorrente retornam:

```json
{
  "data": {},
  "task_id": "celery-task-id-ou-null"
}
```

`task_id = null` nao significa falha de persistencia. Significa que o trabalho nao foi enfileirado naquele momento, por lease ativo ou falha operacional capturada.

## Health de produto

`GET /api/v1/monitored/{product_id}/health` retorna diagnostico operacional:

```json
{
  "product_id": "uuid",
  "domain": "www.mercadolivre.com.br",
  "status": "active",
  "next_check_at": "2026-05-21T12:00:00+00:00",
  "next_check_reason": "scheduled",
  "consecutive_failures": 0,
  "last_successful_collection_at": "2026-05-21T11:00:00+00:00",
  "recent_attempts": []
}
```

## Exemplos de resposta

### GET /api/v1/monitored/ — item da lista

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Notebook Dell Inspiron 15",
  "url_original": "https://www.mercadolivre.com.br/p/MLB123456",
  "url_normalized": "https://www.mercadolivre.com.br/p/MLB123456",
  "status": "active",
  "current_price": "3299.90",
  "is_available": true,
  "next_check_at": "2026-05-21T13:00:00+00:00",
  "next_check_reason": "scheduled",
  "last_checked_at": "2026-05-21T12:00:00+00:00",
  "last_successful_collection_at": "2026-05-21T12:00:00+00:00",
  "last_collection_started_at": "2026-05-21T12:00:00+00:00",
  "last_collection_finished_at": "2026-05-21T12:00:15+00:00",
  "collection_lease_until": null,
  "consecutive_failures": 0,
  "check_interval_minutes": 60,
  "created_at": "2026-05-20T10:00:00+00:00",
  "is_price_stale": false,
  "latest_comparison": {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "monitored_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "reference_available": true,
    "status": "attention",
    "ranking": 2,
    "potential_adjustment": "-300.00",
    "average_price": "3150.00",
    "min_price": "2999.90",
    "max_price": "3399.00",
    "calculated_at": "2026-05-21T12:00:20+00:00",
    "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "run_status": "complete",
    "product_price": "3299.90",
    "participants_count": 3,
    "valid_competitors_count": 3,
    "ignored_competitors_count": 0
  },
  "competitors_count": 3
}
```

### GET /api/v1/comparisons/{monitored_id}

Retorna `MarketSnapshotRead`: campos de mercado sempre presentes + campos da oferta de referência condicionais (`reference_available == true`) + indicadores temporais derivados.

```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "monitored_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "reference_available": true,
  "status": "attention",
  "ranking": 2,
  "potential_adjustment": "-300.00",
  "average_price": "3150.00",
  "min_price": "2999.90",
  "max_price": "3399.00",
  "calculated_at": "2026-05-21T12:00:20+00:00",
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "run_status": "complete",
  "product_price": "3299.90",
  "participants_count": 3,
  "valid_competitors_count": 3,
  "ignored_competitors_count": 0,
  "variation_24h": -2.1,
  "variation_all": 5.3,
  "previous_price": "3370.00",
  "sparkline": [3370.0, 3299.9],
  "market_variation_24h": -1.2,
  "competitors": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "name": "Notebook Dell Inspiron 15 (vendedor B)",
      "current_price": "2999.90",
      "variation_24h": -0.5,
      "status": "active",
      "thumbnail_url": null
    }
  ]
}
```

Quando `reference_available == false`, os campos `status`, `ranking` e `potential_adjustment` retornam `null`.

### GET /api/v1/monitored/{id}/competitors — item da lista

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "monitored_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "url_original": "https://www.mercadolivre.com.br/p/MLB789012",
  "url_normalized": "https://www.mercadolivre.com.br/p/MLB789012",
  "name": "Notebook Dell Inspiron 15 (vendedor B)",
  "status": "active",
  "current_price": "2999.90",
  "is_available": true,
  "last_checked_at": "2026-05-21T12:00:18+00:00",
  "created_at": "2026-05-20T11:00:00+00:00"
}
```

### GET /api/v1/notifications — item da lista

```json
{
  "id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
  "monitored_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "comparison_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "event_type": "price_drop_alert",
  "delivery_status": "sent",
  "title": "Preco caiu: Notebook Dell Inspiron 15",
  "message": "Preco caiu de R$ 3499.90 para R$ 3299.90.",
  "error_message": null,
  "attempt_count": 1,
  "old_price": "3499.90",
  "new_price": "3299.90",
  "old_status": "urgent",
  "new_status": "attention",
  "old_ranking": 3,
  "new_ranking": 2,
  "market_min_old": "2999.90",
  "market_min_new": "2999.90",
  "reason_codes": ["price_drop", "ranking_changed"],
  "competitor_id": null,
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "run_status": "complete",
  "participants_count": 3,
  "sent_at": "2026-05-21T12:00:25+00:00"
}
```

## Compatibilidade

Este contrato e v1. Mudancas de formato, renomeacao de campos, mudanca de status code ou remocao de endpoint exigem nova decisao arquitetural e atualizacao dos consumidores.
