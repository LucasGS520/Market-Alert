# Contrato de Notificacoes

Versao: 1.0  
Proprietario logico: `backend/market_alert/app/notifications` e `backend/market_alert/app/workers/tasks.py`  
Consumidores: frontend, operadores, ntfy.

## Quando gera alerta

Eventos que podem gerar notificacao:

- `price_drop_alert`: preco do produto monitorado caiu pelo menos `NOTIFICATION_DELTA_PERCENT`.
- `price_rise_alert`: preco do produto monitorado subiu pelo menos `NOTIFICATION_DELTA_PERCENT`.
- `competitive_position_alert`: houve mudanca competitiva relevante de status, ranking ou menor preco de mercado.
- `availability_alert`: produto monitorado mudou de disponivel para indisponivel ou vice-versa.

Prioridade de consolidacao:

1. Queda de preco.
2. Alta de preco.
3. Posicao competitiva.

Uma comparacao gera no maximo um alerta consolidado.

## Quando nao gera alerta

Nao enviar notificacao quando:

- `ntfy_topic` nao esta configurado.
- `comparison_task` foi disparada em fluxo `manual`.
- `run_status` e `partial`, `expired` ou `no_competitors`.
- `valid_competitors_count < NOTIFICATION_MIN_QUORUM`.
- Cooldown por produto e tipo de alerta esta ativo.
- Ja existe entrega `sent` para o mesmo `comparison_id` e `alert_type`.
- A comparacao foi deduplicada.
- Nao houve sinais tecnicos suficientes.
- O produto principal esta inelegivel para comparacao.

## Cooldown

Chave Redis:

```text
cooldown:notify:{monitored_id}:{event_type}
```

TTL padrao: `NOTIFICATION_COOLDOWN_MINUTES`.

Cooldown e granular por produto e tipo de alerta. Um alerta de preco nao bloqueia necessariamente outro tipo de alerta do mesmo produto.

## Quorum minimo

Configuracao: `NOTIFICATION_MIN_QUORUM`.

Comparacao pode ser persistida com poucos ou nenhum concorrente valido para auditoria, mas notificacao competitiva exige quorum minimo.

## Deduplicacao

Ha dois niveis:

- Snapshot de comparacao identico dentro da janela de deduplicacao nao e persistido.
- Entrega de notificacao ja enviada para a mesma comparacao e tipo de alerta nao e repetida.

## Exemplo de payload interno

```json
{
  "monitored_id": "uuid",
  "comparison_id": "uuid",
  "alert_type": "price_drop_alert",
  "reason_codes": ["price_drop", "ranking_changed"],
  "old_price": "129.90",
  "new_price": "119.90",
  "old_status": "attention",
  "new_status": "competitive",
  "old_ranking": 2,
  "new_ranking": 1,
  "market_min_old": "125.00",
  "market_min_new": "119.90",
  "run_id": "uuid",
  "run_status": "complete",
  "participants_count": 4
}
```

## Diagnostico de ausencia de notificacao

Verificar nesta ordem:

1. `ntfy_topic` esta configurado?
2. Houve `comparison_task` depois da coleta?
3. A comparacao persistiu ou foi deduplicada?
4. `run_status` e `complete`?
5. `valid_competitors_count` atende `NOTIFICATION_MIN_QUORUM`?
6. Houve variacao maior ou igual a `NOTIFICATION_DELTA_PERCENT`?
7. Ranking mudou de forma relevante?
8. Cooldown esta ativo no Redis?
9. Ja existe `notification_logs.delivery_status = sent` para a mesma comparacao e alerta?
10. A task `notification_task` foi enfileirada e executada?
