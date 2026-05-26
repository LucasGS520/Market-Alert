# Contrato de Notificações

Versão: 2.0  
Proprietário lógico: `app/notifications/` + `app/workers/tasks.py`  
Fonte de verdade de tipos: `app/notifications/event_types.py` (backend) e `src/constants/notificationTypes.js` (frontend)

---

## Taxonomia de tipos

Os tipos são agrupados em cinco categorias. Somente tipos **ACTIVE** podem ser entregues via ntfy.
A fonte de verdade em código é `app/notifications/event_types.py`.

### ACTIVE — gerados pelo pipeline atual

| Tipo | Gerado em | Descrição |
|------|-----------|-----------|
| `competitive_threat_alert` | `_decide_alert()` em `tasks.py` | Posição competitiva piorou (ranking, status ou gap) |
| `competitive_opportunity_alert` | `_decide_alert()` em `tasks.py` | Posição melhorou ou mercado ficou menos agressivo |
| `market_movement_alert` | `_decide_alert()` em `tasks.py` | Menor preço de mercado mudou sem impacto direto na posição |
| `reference_availability_alert` | `_decide_alert()` em `tasks.py` | Produto de referência ficou disponível ou indisponível |
| `availability_alert` | `collector_task` direto | Produto monitorado mudou disponibilidade |

### DEPRECATED — pipeline antigo, não gerados hoje

Podem existir em `notification_logs` como histórico. Nenhum caminho em `tasks.py` os produz hoje.
`send_notification()` os aceita (não são `AUDIT_ONLY`), mas nunca chegam lá na prática.

`price_drop_alert`, `price_rise_alert`, `competitive_position_alert`, `market_alert`, `error_alert`

### AUDIT_ONLY — nunca entregue ao usuário

| Tipo | Gerado por | Descrição |
|------|-----------|-----------|
| `collection_health_alert` | `registrar_supressao()` | Marcador de supressão pré-decisão (rodada degradada, quorum insuficiente) |

`send_notification()` rejeita qualquer tentativa de entregar `AUDIT_ONLY_TYPES` — levanta `ValueError`.

### INACTIVE — definidos no schema DB, sem lógica de geração ainda

| Tipo | Previsto para |
|------|--------------|
| `competitor_movement_alert` | Tier 2: concorrente específico mudou posição |
| `competitor_availability_alert` | Tier 2: concorrente específico mudou disponibilidade |

### LEGACY — apenas leitura histórica

`price_drop`, `price_rise`, `status_change`, `ranking_change`, `product_unavailable`, `product_available`, `market_price_drop`, `market_price_rise`, `competitor_unavailable`, `competitor_available`.

Não são gerados pelo pipeline atual. Existem apenas para não quebrar queries sobre dados históricos.

---

## Hierarquia de sinais → alerta

`comparison_task` coleta sinais técnicos da comparação e aplica a hierarquia abaixo. **Uma comparação gera no máximo um alerta público** — o sinal de maior impacto competitivo vence.

| Sinal técnico | Gera |
|---------------|------|
| `ranking_worsened` / `status_worsened` / `gap_increased` | `competitive_threat_alert` |
| `ranking_improved` / `status_improved` / `market_became_less_aggressive` / `gap_decreased` | `competitive_opportunity_alert` |
| `market_min_changed` / `market_became_more_aggressive` | `market_movement_alert` |
| `reference_became_unavailable` / `reference_became_available` | `reference_availability_alert` |

Prioridade: Threat > Opportunity > MarketMovement > ReferenceAvailability.

---

## Supressões

| Caminho | `skip_reason` | Observabilidade |
|---------|--------------|----------------|
| `ntfy_topic` não configurado | — | log DEBUG |
| `run_status == "manual"` | — | log INFO |
| `run_status` em {partial, expired, no_competitors} | `degraded_run` | log INFO + registro em `notification_logs` (`delivery_status='skipped'`) |
| `valid_competitors_count < NOTIFICATION_MIN_QUORUM` | `insufficient_quorum` | log INFO + registro em `notification_logs` (`delivery_status='skipped'`) |
| Cooldown ativo por (produto × tipo) | `cooldown_active` | log INFO (`notificacao_suprimida`) |
| Já entregue para o mesmo (comparison_id, event_type) | `deduplicated` | log INFO (`notificacao_suprimida`) |

Registros em `notification_logs` com `delivery_status='skipped'` usam `event_type='collection_health_alert'` e têm o campo `skip_reason` preenchido.

---

## Cooldown

Chave Redis por (produto × tipo de alerta):

```
cooldown:notify:{monitored_id}:{event_type}
```

TTL: `NOTIFICATION_COOLDOWN_MINUTES` (padrão 30 min). Um hit de cooldown em `price_drop_alert` não bloqueia `competitive_threat_alert` do mesmo produto.

---

## Diagnóstico de ausência de notificação

1. `ntfy_topic` está configurado no `.env`?
2. A `comparison_task` foi disparada após a coleta?
3. `run_status == "complete"` na comparação?
4. `valid_competitors_count >= NOTIFICATION_MIN_QUORUM`?
5. Houve sinais técnicos na comparação (`reason_codes` preenchido)?
6. Cooldown ativo? — `GET cooldown:notify:{monitored_id}:{event_type}` no Redis
7. Já existe registro `delivery_status='sent'` para a mesma comparação e tipo?
8. A `notification_task` foi enfileirada e executada (checar logs do worker)?
9. Existe registro `delivery_status='skipped'` com `skip_reason` em `notification_logs`?
