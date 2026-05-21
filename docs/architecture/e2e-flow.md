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

1. A coleta bem-sucedida do produto principal cria uma rodada em Redis quando existem concorrentes elegiveis.
2. Chave: `collection_run:{run_id}`.
3. Cada concorrente recebe `collector_task(competitor_id=..., run_id=...)`.
4. Concorrentes terminam como `done`, `failed`, `deferred` ou `skipped`.
5. `comparison_task(..., run_id=...)` aguarda a rodada sair de `pending`.
6. Se o TTL expirar, a comparacao segue com os dados disponiveis e status degradado.

## Comparacao

1. `calculate_comparison` valida produto principal.
2. Produto sem preco, inativo ou indisponivel aborta comparacao.
3. Concorrentes validos entram no calculo.
4. Concorrentes invalidos sao ignorados, mas contam como metadado de auditoria.
5. O snapshot registra ranking, status competitivo, preco medio, minimo, maximo e contadores.
6. Snapshot identico dentro da janela de deduplicacao nao e persistido.
7. Snapshot novo invalida cache de comparacao.

## Notificacao

1. A comparacao calcula sinais tecnicos.
2. Sinais sao consolidados em no maximo um alerta publico por comparacao.
3. A notificacao e bloqueada quando a rodada e manual, degradada ou sem quorum minimo.
4. `notification_task` entrega via ntfy se configurado.
5. Tentativas de entrega sao registradas em PostgreSQL.
6. Cooldown por produto e tipo de alerta e gravado em Redis.

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
