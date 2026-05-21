# Contrato API v1

Versao: 1.0  
Proprietario logico: `market_alert/app/api/v1`  
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

## Compatibilidade

Este contrato e v1. Mudancas de formato, renomeacao de campos, mudanca de status code ou remocao de endpoint exigem nova decisao arquitetural e atualizacao dos consumidores.
