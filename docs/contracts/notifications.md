# Contrato de Notificações

Versão: 3.0  
Proprietário lógico: `app/notifications/` + `app/workers/tasks.py`  
Fonte de verdade de tipos: `app/notifications/event_types.py` (backend) e `src/constants/notificationTypes.js` (frontend)

---

## Taxonomia de tipos

Dois conjuntos mutuamente exclusivos. A fonte de verdade em código é `app/notifications/event_types.py`.

### DELIVERABLE_ALERT_TYPES — entregues ao usuário via ntfy

| Tipo | Gerado por | Assunto |
|------|-----------|---------|
| `competitive_threat_alert` | `decide_alert()` | Posição competitiva piorou (ranking, status ou gap) |
| `competitive_opportunity_alert` | `decide_alert()` | Posição melhorou ou mercado ficou menos agressivo |
| `market_movement_alert` | `decide_alert()` | Menor preço de mercado mudou sem impacto direto na posição |
| `reference_availability_alert` | `decide_alert()` | Produto de referência mudou disponibilidade |
| `competitor_price_movement_alert` | fallback de concorrente | Concorrente específico teve variação de preço relevante |
| `competitor_availability_alert` | fallback de concorrente | Concorrente específico mudou disponibilidade |

### AUDIT_EVENT_TYPES — nunca entregues ao usuário

| Tipo | Gerado por | Significado |
|------|-----------|-------------|
| `notification_suppressed` | `registrar_supressao()` | Comparação bloqueada antes de avaliar sinais (rodada degradada ou quorum insuficiente) |

`send_notification()` rejeita qualquer tentativa de entregar `AUDIT_EVENT_TYPES` — levanta `ValueError`.

---

## Fluxo de decisão por comparação

Uma comparação elegível gera **no máximo uma** `notification_task`.

```
build_signals(snapshot_anterior, snapshot_atual)
  └─ decide_alert(sinais)
       ├─ Decisão encontrada → enfileira notification_task (alerta primário)
       └─ None (sem sinais primários)
            └─ build_competitor_signals(concorrentes)
                 ├─ Sinal encontrado → enfileira notification_task (concorrente como evento principal)
                 └─ Sem sinais → sem notificação (log debug)
```

---

## Hierarquia de sinais → alerta

`decide_alert()` aplica a hierarquia abaixo sobre os sinais técnicos. O primeiro grupo ativado vence.

| Sinais técnicos | Alerta gerado |
|----------------|---------------|
| `ranking_worsened` / `status_worsened` / `gap_increased` | `competitive_threat_alert` |
| `ranking_improved` / `status_improved` / `market_became_less_aggressive` / `gap_decreased` | `competitive_opportunity_alert` |
| `market_min_changed` / `market_became_more_aggressive` | `market_movement_alert` |
| `reference_became_unavailable` / `reference_became_available` | `reference_availability_alert` |

Prioridade: Threat > Opportunity > MarketMovement > ReferenceAvailability.

Se nenhum sinal primário for detectado, o pipeline avalia concorrentes:

| Sinal do concorrente | Alerta gerado |
|---------------------|---------------|
| `price_movement` (variação ≥ threshold) | `competitor_price_movement_alert` |
| `availability_change` | `competitor_availability_alert` |

Quando há múltiplos concorrentes com sinal, `price_movement` tem prioridade sobre `availability_change`. O concorrente escolhido como principal é registrado em `competitor_id` do `NotificationLog`.

---

## Sinais que não geram alerta

Os sinais abaixo entram em `reason_codes` (auditoria) mas não disparam alerta sozinhos:

- `reference_price_drop` / `reference_price_rise` — variação de preço da referência sem impacto na posição competitiva.
- Primeiro snapshot — sem snapshot anterior, nenhum sinal temporal é gerado.

---

## Gates de supressão

| Caminho | `skip_reason` | Observabilidade |
|---------|--------------|----------------|
| `ntfy_topic` não configurado | — | log DEBUG |
| `run_status == "manual"` | — | log INFO (silencioso, sem registro em DB) |
| `run_status` em {partial, expired, no_competitors} | `degraded_run` | log INFO + `notification_suppressed` em `notification_logs` |
| `valid_competitors_count < NOTIFICATION_MIN_QUORUM` | `insufficient_quorum` | log INFO + `notification_suppressed` em `notification_logs` |
| Cooldown ativo por (produto × tipo) | `cooldown_active` | log INFO (sem registro em DB) |
| Já entregue para o mesmo (comparison_id, event_type) | `deduplicated` | log INFO (sem registro em DB) |

Registros com `delivery_status='skipped'` usam `event_type='notification_suppressed'` e têm `skip_reason` preenchido. Supressões por cooldown e dedupe não são persistidas — apenas logadas.

---

## Cooldown

Chave Redis por produto × tipo de alerta:

```
cooldown:notify:{monitored_id}:{event_type}
```

TTL: `NOTIFICATION_COOLDOWN_MINUTES` (padrão 30 min). Um cooldown em `competitive_threat_alert` não bloqueia `reference_availability_alert` do mesmo produto.

---

## Deduplicação

Índice único em `notification_logs`:

```sql
UNIQUE (comparison_id, event_type) WHERE comparison_id IS NOT NULL AND delivery_status = 'sent'
```

Garante no máximo uma entrega bem-sucedida por comparação. O comportamento é complementar ao cooldown — cooldown opera por produto no Redis, dedupe opera por snapshot no PostgreSQL.

---

## Diagnóstico de ausência de notificação

1. `ntfy_topic` está configurado no `.env`?
2. A `comparison_task` foi disparada após a coleta?
3. `run_status == "complete"` na comparação?
4. `valid_competitors_count >= NOTIFICATION_MIN_QUORUM`?
5. Houve sinais técnicos (`reason_codes` preenchido na comparação)?
6. Cooldown ativo? — `GET cooldown:notify:{monitored_id}:{event_type}` no Redis
7. Já existe registro `delivery_status='sent'` para a mesma `comparison_id`?
8. A `notification_task` foi enfileirada e executada (checar logs do worker)?
9. Existe registro `delivery_status='skipped'` com `skip_reason` em `notification_logs`?
