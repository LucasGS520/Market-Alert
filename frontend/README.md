# Frontend

UI estatica do Market Alert. Este modulo e servido pelo Nginx e consome a API em `/api/v1`, que o `frontend/nginx.conf` encaminha para o backend FastAPI.

Este README descreve apenas o servico de frontend. A governanca oficial de arquitetura, contratos e operacao fica no [README raiz](../README.md).

## Como carrega

O ponto de entrada continua sendo `index.html`.

- React, ReactDOM e Babel standalone sao carregados via CDN.
- Os arquivos JSX sao carregados por `<script type="text/babel">`.
- Nao existe bundler, build step, router externo ou gerenciador de estado.
- Componentes e helpers compartilhados continuam expostos em `window` via `Object.assign(window, ...)`.

A ordem dos scripts em `index.html` e parte do contrato operacional: API e formatadores carregam primeiro, depois componentes base, layout, overlays, telas e por ultimo `src/app/App.jsx`.

## Mapa de diretorios

- `assets/`: logos e imagens estaticas.
- `styles/`: CSS global da UI.
- `src/api/`: cliente HTTP, mapeamento de payloads e formatadores.
- `src/components/`: componentes reutilizaveis sem responsabilidade de tela.
- `src/layout/`: estrutura fixa da aplicacao, como sidebar e topbar.
- `src/screens/`: telas principais renderizadas pelo `App`.
- `src/overlays/`: modal e drawer.

## Contrato por tela

- Dashboard (`src/screens/dashboard`): lista produtos, notificacoes e historico de preco agregado pelo cliente.
- Monitoramento (`src/screens/monitors`): lista produtos e aplica filtros locais.
- Alertas (`src/screens/alerts`): lista tentativas de notificacao retornadas por `/api/v1/notifications`.
- Detalhe do produto (`src/screens/product-detail`): carrega produto, concorrentes, historico, health de coleta e acoes de pause/resume/delete.

## Marketplace

Mercado Livre e o unico marketplace oficialmente suportado no frontend. Qualquer copy ou metadado visual para outros marketplaces deve ser tratado como inconsistencia historica ou compatibilidade visual nao oficial, sem ampliar suporte funcional.

## Regra de manutencao

Ao adicionar uma tela ou componente, preserve a UI estatica atual. Nao introduza Vite, npm, TypeScript, import/export ESM ou build step nesta etapa sem uma decisao arquitetural explicita.

Mudancas que alterem carregamento, contrato com a API ou promessa de marketplace devem atualizar o README raiz, os contratos em `docs/` e uma ADR quando houver decisao arquitetural nova.
