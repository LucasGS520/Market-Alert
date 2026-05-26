# Fluxo E2E Oficial

Versao: 1.0  
Fonte de verdade: comportamento observado no runtime atual e codigo em `frontend`, `backend/market_alert` e `backend/market_scraper`.

## Visao geral

O sistema opera como uma pipeline assincrona:

1. A UI estatica consulta e exibe dados.
2. A API valida entrada, persiste entidades e agenda trabalho.
3. Workers Celery executam coleta, comparacao, scheduler e notificacao.
4. O scraper extrai dados do Mercado Livre.
5. PostgreSQL guarda fatos duraveis.
6. Redis coordena estado operacional transitorio.

## Cadastro de produto

1. O usuario cadastra uma URL no frontend.
2. O frontend chama `POST /api/v1/monitored/`.
3. A API normaliza e valida a URL.
4. URL invalida retorna `400` com detalhe `invalid_url`.
5. Produto valido e persistido como `pending`.
6. A API tenta enfileirar a primeira coleta com lease.
7. A resposta HTTP e `202 Accepted` com `data` e `task_id`.

## Coleta principal

1. `collector_task(product_id=...)` executa na fila `collection`.
2. A task ignora produto inexistente, `paused` ou `unsupported`.
3. O service de dominio chama `market_scraper` via HTTP.
4. O scraper detecta marketplace e usa o adapter do Mercado Livre.
5. Resultado valido gera historico de preco e atualiza estado do produto.
6. Erro semantico atualiza status e reagendamento conforme classificacao.
7. Mudanca de disponibilidade do produto pode enfileirar `availability_alert`.

## Rodada coordenada

1. O `collection_orchestrator_task` tenta coletar a oferta de referencia (MonitoredProduct).
2. Falha na coleta da referencia **nao aborta** a rodada — apenas torna sua posicao indisponivel no snapshot.
3. A rodada so e abortada por: produto inexistente, `paused`/`unsupported`, scraper completamente indisponivel, ou produto deletado durante a coleta.
4. Quando existem concorrentes elegiveis, o orquestrador cria uma rodada coordenada no Redis.
5. Chave: `collection_run:{run_id}`.
6. Cada concorrente recebe `collector_task(competitor_id=..., run_id=...)`.
7. Concorrentes terminam como `done`, `failed`, `deferred` ou `skipped`.
8. `comparison_task(..., run_id=...)` aguarda a rodada sair de `pending`.
9. Se o TTL expirar, a comparacao segue com os dados disponiveis e status degradado.

## Comparacao

O snapshot representa o **mercado monitorado**, nao apenas o produto monitorado.

1. `calculate_comparison` verifica a ancora estrutural (MonitoredProduct).
2. Produto inexistente ou `paused`/`unsupported` aborta a comparacao.
3. A elegibilidade da oferta de referencia e avaliada separadamente:
   - Referencia elegivel: `status == "active"`, `is_available == True`, `current_price != None`.
   - Referencia inelegivel: mercado continua; `ranking`, `status` e `potential_adjustment` ficam `None` no snapshot.
4. Zero ofertas validas no total (referencia + concorrentes) aborta a comparacao.
5. Concorrentes validos entram no calculo de mercado.
6. Concorrentes invalidos sao ignorados, mas contam como metadado de auditoria.
7. O snapshot registra precos de mercado (min, max, media), posicao da referencia (quando disponivel) e contadores.
8. `reference_available: bool` indica explicitamente se a referencia participou do snapshot.
9. Snapshot identico dentro da janela de deduplicacao nao e persistido.
10. Snapshot novo invalida cache de comparacao.

## Notificacao

1. A comparacao coleta sinais tecnicos separados por classe:
   - **Sinais da referencia**: `price_drop`, `price_rise`, `status_changed`, `ranking_changed`.
   - **Sinais de mercado**: `market_min_changed`.
2. Sinais sao consolidados em no maximo um alerta publico por comparacao, por classe:
   - Sinais de preco da referencia → `price_drop_alert` ou `price_rise_alert`.
   - Sinais de posicao da referencia → `competitive_position_alert`.
   - Sinais de mercado sem referencia → `market_alert`.
3. Sinais da referencia so sao coletados quando `reference_available == True`.
4. A notificacao e bloqueada quando a rodada e manual, degradada ou sem quorum minimo.
5. `notification_task` entrega via ntfy se configurado.
6. Tentativas de entrega sao registradas em PostgreSQL.
7. Cooldown por produto e tipo de alerta e gravado em Redis.

## Leitura pela UI

O frontend monta a experiencia com chamadas separadas:

- Produtos e ultima comparacao.
- Notificacoes.
- Historico de preco por produto ou concorrente.
- Health de coleta no detalhe do produto.

A UI nao deve carregar regra critica de negocio. Calculos visuais derivados podem existir, mas a persistencia e as decisoes de negocio ficam no backend.

## Garantia de nao regressao

Toda mudanca organizacional deve preservar:

- Mesmos endpoints publicos.
- Mesmos status codes.
- Mesmos payloads documentados.
- Mesmas filas e tasks.
- Mesma separacao PostgreSQL duravel / Redis transitorio.
- Mercado Livre como unico marketplace oficial.

### Invariantes do modelo de mercado (nao regredir)

- O snapshot de mercado deve ser calculado mesmo quando a oferta de referencia estiver indisponivel.
- `ranking`, `status` e `potential_adjustment` so devem ser preenchidos quando `reference_available == True`.
- Sinais da referencia (`status_changed`, `ranking_changed`) nao devem disparar quando `comparacao.status is None`.
- `market_alert` e `competitive_position_alert` sao classes distintas; nao misturar causas.
