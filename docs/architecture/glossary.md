# Glossario e Nomes Canonicos

Versao: 1.0

## Entidades

- Produto monitorado (`MonitoredProduct`): produto principal acompanhado pelo usuario.
- Concorrente (`Competitor`): produto usado para comparacao competitiva contra um produto monitorado.
- Historico de preco (`PriceHistory`): registro duravel de uma coleta.
- Comparacao (`Comparison`): snapshot competitivo persistido depois de coleta ou recalculo.
- Log de notificacao (`NotificationLog`): tentativa duravel de entrega de alerta.

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

- `price_drop_alert`: queda de preco do produto monitorado acima do threshold.
- `price_rise_alert`: alta de preco do produto monitorado acima do threshold.
- `competitive_position_alert`: mudanca competitiva relevante.
- `availability_alert`: mudanca de disponibilidade do produto.
- `error_alert`: alerta operacional de problema de coleta quando usado.

## Sinais tecnicos

- `price_drop`: preco do produto caiu.
- `price_rise`: preco do produto subiu.
- `status_changed`: status competitivo mudou.
- `ranking_changed`: ranking mudou de forma relevante.
- `market_min_changed`: menor preco de mercado mudou acima do threshold.
- `product_unavailable`: produto ficou indisponivel.
- `product_available`: produto voltou a ficar disponivel.

## Marketplaces

- `mercadolivre`: unico marketplace oficialmente suportado.
- Outros dominios devem ser tratados como nao suportados ate existir adapter validado e ADR aprovada.

## Estado duravel e operacional

- Duravel: dado necessario para auditoria, historico ou reconstituicao de negocio. Deve ficar em PostgreSQL.
- Operacional: dado transitorio de coordenacao, lock, fila, cooldown, cache ou tentativa recente. Deve ficar em Redis.
