# Matriz de Responsabilidade por Camada

Versao: 1.0

Cada camada tem um dono logico e um conjunto de responsabilidades exclusivas. Qualquer logica que esteja fora do seu dono e candidata a refatoracao.

---

## Camadas e Responsabilidades

### API (`app/api/v1/`)

**Dono logico:** contratos de entrada e saida HTTP.

Responsabilidades:
- Validar entrada (URL, parametros, tipos).
- Chamar services ou workers — nunca calcular estado de mercado diretamente.
- Serializar resposta usando schemas de leitura (`*Read`, `MarketSnapshotRead`).
- Retornar codigos HTTP semanticamente corretos.

Nao deve:
- Conter logica de mercado, sinais de alerta ou regras de agendamento.
- Ler modelos de banco diretamente sem passar por service.

---

### Service de dominio (`app/products/`, `app/comparison/`, `app/notifications/`, `app/scheduling/`)

**Dono logico:** regras de negocio e persistencia.

Responsabilidades:
- `comparison_service`: calcular e persistir snapshots de mercado; determinar `reference_available`; deduplicar snapshots identicos.
- `market_indicators_service`: derivar indicadores temporais (variation_24h, sparkline) a partir de PriceHistory e Comparison. Sem persistencia.
- `scheduler_service`: encontrar produtos elegiveis, adquirir lease atomico, enfileirar coleta.
- `notifications_service`: entregar alerta via ntfy; registrar tentativa; verificar cooldown.
- `monitored_service`, `competitor_service`: coletar preco, atualizar estado de entidade.

Nao deve:
- Invalidar cache Redis (responsabilidade do worker).
- Enfileirar tasks Celery diretamente (responsabilidade do worker ou da API em casos especificos como criacao).
- Calcular `next_check_at` fora do `scheduler_service`.

---

### Worker (`app/workers/`)

**Dono logico:** orquestracao assincrona e coordenacao de rodada.

Responsabilidades:
- `collection_orchestrator_task`: orquestrar a rodada de mercado (referencia + concorrentes + comparacao); liberar lease.
- `collector_task`: coleta unitaria de produto ou concorrente; marcar status na rodada Redis.
- `comparison_task`: aguardar rodada, chamar `calculate_comparison`, coletar sinais, consolidar e enfileirar notificacao. Invalidar cache.
- `notification_task`: chamar `send_notification` com retry/backoff.
- `scheduler_task`: protetor por lock global; delega ao `scheduler_service`.

Nao deve:
- Conter logica de calculo de mercado (pertence ao service).
- Persistir dados de negocio diretamente — use sessions e services.

---

### Scheduler / Policy (`app/scheduling/`)

**Dono logico:** decisao de quando coletar.

Responsabilidades:
- `policy.classify_stability`: classificar nivel de estabilidade do mercado com base em eventos de mudanca (preco, disponibilidade, mercado).
- `policy.compute_next_check`: calcular proximo horario e delay com base na estabilidade.
- `scheduler_service.run_scheduler`: batch de elegibilidade, lease e enqueue.

Nao deve:
- Usar estado interno do produto como unica fonte para decidir estabilidade (deve incluir `last_market_changed_at`).
- Enfileirar tasks sem adquirir lease atomico.

---

### Notification (`app/notifications/`)

**Dono logico:** entrega e auditoria de alertas.

Responsabilidades:
- `notifications_service.send_notification`: verificar cooldown, montar mensagem, entregar via ntfy, registrar tentativa.
- `_decide_alert` (em `workers/tasks.py`): consolidar N sinais tecnicos em 1 tipo de alerta publico. Mora no worker porque depende de estado da comparacao, nao do service de notificacao.

Nao deve:
- Alterar preco, ranking ou status competitivo (consequencia, nao causa).
- Receber decisao sobre elegibilidade de snapshot (essa decisao e do worker).

---

### Frontend (`frontend/src/`)

**Dono logico:** exibicao e interacao. Sem logica de mercado.

Responsabilidades:
- `api/client.js`: buscar dados da API; nao calcular indicadores.
- `api/mappers.js`: normalizar payload da API para modelo de tela (conversao de tipos, campos opcionais).
- `api/formatters.js`: formatar valores para exibicao (brl, relativeTime).
- Telas: interpretar campos semanticos do backend (`reference_available`, `run_status`, `status`) para decidir o que exibir.

Nao deve:
- Calcular `variation_24h`, `sparkline`, `market_variation_24h` — esses campos chegam prontos do backend.
- Inferir elegibilidade de alerta, quorum ou estabilidade — essas decisoes pertencem ao backend.
- Usar `current_price` do produto para calcular posicao competitiva — use os campos do snapshot de mercado.

---

## Regra de Nao-Invasao de Camada

| Origem | Destino proibido |
|---|---|
| API route | Logica de mercado ou calculo de snapshot |
| Service de dominio | Invalidacao de cache ou enqueue de tasks |
| Worker | Persistencia direta sem session/service |
| Frontend | Calculo de indicadores ou regras de elegibilidade |
| Notification service | Decisao sobre elegibilidade de snapshot |

---

## Contrato de Compatibilidade para Transicao

Durante a transicao para o modelo orientado a mercado, os seguintes contratos devem ser preservados:

1. Campos legados (`status`, `ranking`) continuam presentes na resposta da API; ficam `null` quando `reference_available == False` — nao sao removidos.
2. Novos campos (`reference_available`, `market_variation_24h`, `competitors`) sao aditivos — nenhum consumidor existente quebra por recebe-los.
3. `run_status` e exposto na API para auditoria; a UI usa-o apenas para exibicao, nunca para recalculo.
4. `notification_min_quorum` pode ser ajustado por configuracao sem mudanca de codigo.
5. O pipeline de notificacao bloqueia para snapshots degradados (`partial`, `no_competitors`, `expired`) — esse comportamento nao deve ser desativado sem ADR aprovada.
