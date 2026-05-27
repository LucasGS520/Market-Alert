# Glossario e Nomes Canonicos

Versao: 1.1

## Entidades

- Produto monitorado (`MonitoredProduct`): ancora de identidade, ciclo de vida e contexto do usuario. Nao e a fonte unica da verdade operacional — e o ponto de entrada do dominio, nao o decisor de mercado.
- Concorrente (`Competitor`): fonte de formacao do mercado vinculada a um produto monitorado. Nao e apendice do produto: e participante ativo do mercado observado.
- Historico de preco (`PriceHistory`): registro duravel e factual de cada coleta. Base para calculo de indicadores temporais.
- Comparacao (`Comparison`): snapshot de mercado persistido apos cada rodada de coleta. Contem dados do mercado consolidado e, condicionalmente, a posicao da oferta de referencia nesse mercado.
- Log de notificacao (`NotificationLog`): tentativa duravel de entrega de alerta. Consequencia do snapshot, nunca origem.

## Conceitos de Mercado

- Oferta de referencia: o produto monitorado considerado como participante do mercado. Sua participacao e condicional — so entra no snapshot quando `status == active`, `is_available == True` e `current_price != None`. Quando ausente, o mercado ainda pode existir.
- Estado de mercado: conjunto derivado de preco minimo, maximo, medio, contagem de participantes e status da rodada. Calculado sempre que houver pelo menos uma oferta valida (referencia ou concorrente). Representado pelos campos de mercado do `Comparison`.
- Mercado consolidado: o estado de mercado de uma rodada especifica, pronto para ser usado como base de decisao operacional (agendamento, comparacao, alerta).
- Snapshot elegivel: um `Comparison` cujo `run_status` e `complete` e `valid_competitors_count >= notification_min_quorum`. Apenas snapshots elegiveis geram notificacoes.
- Rodada degradada: rodada cujo `run_status` e `partial`, `no_competitors` ou `expired`. O snapshot e persistido para auditoria, mas o pipeline de notificacao e bloqueado.
- Sinal de alerta: sinal tecnico derivado da comparacao de dois snapshots consecutivos. Multiplos sinais sao avaliados em hierarquia — o primeiro grupo ativado gera um unico alerta publico por comparacao.
- Ciclo de vida do produto: conjunto de transicoes de status do produto monitorado (`pending`, `active`, `unavailable`, `error`, `paused`, `unsupported`). Controlado pela coleta e pelo usuario, nao pelo mercado.
- Decisao operacional: acao tomada com base no estado de mercado — agendamento da proxima coleta, elegibilidade de notificacao, calculo de tendencia e estabilidade. Distinta da gestao do ciclo de vida do produto.

## Estados de produto e concorrente

- `pending`: cadastrado e aguardando primeira coleta.
- `active`: ultima coleta bem-sucedida.
- `unavailable`: produto reconhecido, mas indisponivel.
- `error`: ultima coleta falhou com erro recuperavel.
- `paused`: monitoramento suspenso manualmente.
- `unsupported`: marketplace nao suportado ou URL inelegivel.

## Estados de rodada

- `pending`: ainda existem concorrentes pendentes.
- `complete`: todos terminaram com sucesso ou foram pulados por inelegibilidade esperada.
- `partial`: todos terminaram, mas houve `failed` ou `deferred`.
- `expired`: Redis expirou a rodada antes de todos terminarem.
- `no_competitors`: rodada sem concorrentes validos.

## Filas e tasks

- Fila `collection`: coleta de produto ou concorrente.
- Fila `comparison`: calculo de snapshot competitivo.
- Fila `notification`: entrega de alerta.
- Fila `default`: suporte a tarefas gerais quando aplicavel.
- `collector_task`: coleta produto monitorado ou concorrente.
- `comparison_task`: recalcula comparacao e avalia sinais de notificacao.
- `notification_task`: entrega alerta consolidado.
- `scheduler_task`: encontra produtos vencidos e enfileira coleta com lease.

## Alertas

Tipos entregues ao usuario (ver `event_types.DELIVERABLE_ALERT_TYPES`):

- `competitive_threat_alert`: posicao competitiva piorou — ranking, status ou gap em relacao ao mercado.
- `competitive_opportunity_alert`: posicao melhorou ou mercado ficou menos agressivo.
- `market_movement_alert`: menor preco de mercado mudou sem impacto direto na posicao da referencia.
- `reference_availability_alert`: produto de referencia mudou disponibilidade.
- `competitor_price_movement_alert`: concorrente especifico teve variacao de preco relevante.
- `competitor_availability_alert`: concorrente especifico mudou disponibilidade.

Evento de auditoria (ver `event_types.AUDIT_EVENT_TYPES`) — nunca entregue ao usuario:

- `notification_suppressed`: registra supressoes operacionais (rodada degradada, quorum insuficiente).

## Sinais tecnicos

Sinais primarios (avaliados por `build_signals()` e `decide_alert()`):

- `ranking_worsened` / `ranking_improved`: ranking do produto monitorado piorou ou melhorou.
- `status_worsened` / `status_improved`: status competitivo degradou ou melhorou.
- `gap_increased` / `gap_decreased`: distancia para o preco minimo de mercado aumentou ou diminuiu.
- `market_became_more_aggressive` / `market_became_less_aggressive`: mercado ficou mais ou menos agressivo.
- `market_min_changed`: menor preco de mercado mudou acima do threshold.
- `reference_became_unavailable` / `reference_became_available`: produto de referencia mudou disponibilidade.
- `reference_price_drop` / `reference_price_rise`: variacao de preco da referencia — entram em `reason_codes`, mas nao geram alerta sozinhos.

Sinais de concorrente (avaliados por `build_competitor_signals()`, fallback quando nenhum sinal primario gera alerta):

- `price_movement`: concorrente teve variacao de preco relevante.
- `availability_change`: concorrente mudou disponibilidade.

## Marketplaces

- `mercadolivre`: unico marketplace oficialmente suportado.
- Outros dominios devem ser tratados como nao suportados ate existir adapter validado e ADR aprovada.

## Politica de Decisao

O produto monitorado governa: identidade (nome, URL), ciclo de vida (status, pause/resume), contexto de navegacao e auditoria.

O mercado consolidado governa: proxima checagem (via estabilidade de mercado), elegibilidade de notificacao (quorum, run_status), calculo de tendencia e alertas economicos.

Regra de separacao: nenhuma camada deve usar o estado interno do produto monitorado para tomar decisoes que pertencem ao mercado. O produto fornece a ancora; o snapshot fornece a verdade operacional.

## Estado duravel e operacional

- Duravel: dado necessario para auditoria, historico ou reconstituicao de negocio. Deve ficar em PostgreSQL.
- Operacional: dado transitorio de coordenacao, lock, fila, cooldown, cache ou tentativa recente. Deve ficar em Redis.
