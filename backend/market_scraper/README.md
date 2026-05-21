# market_scraper

`market_scraper` e o microservico responsavel por extrair dados de produto do marketplace oficialmente suportado. Nesta versao, o unico marketplace suportado e Mercado Livre.

Este README detalha o servico, mas a governanca de fluxo, contratos e decisoes fica no [README raiz](../README.md).

## Responsabilidade

- Receber uma URL de produto.
- Detectar o marketplace suportado.
- Executar o adapter apropriado.
- Usar Playwright/browser session quando necessario.
- Retornar `ScrapeResult` estruturado ou `ScrapeError` semantico.

O scraper nao decide comparacao, agendamento, notificacao ou persistencia de negocio.

## Mapa de diretorios

- `app/main.py`: FastAPI, lifespan do browser, health checks e endpoint `/scraper/parse`.
- `app/router.py`: deteccao de marketplace e selecao de adapter.
- `app/adapters/`: adapters por marketplace. Hoje apenas `mercadolivre`.
- `app/scraping/`: browser, coleta e extracao.
- `app/schemas.py`: contrato de sucesso, erro, metodos de extracao e confidence minima.
- `app/core/config.py`: configuracoes operacionais.

## Marketplace

Mercado Livre e o unico marketplace oficialmente suportado:

- `mercadolivre.com.br`
- `mercadolibre.com`

Adicionar outro marketplace exige adapter validado e contrato atualizado.

## Regra de manutencao

- Nao acoplar scraping a notificacao ou comparacao.
- Nao persistir estado de negocio no scraper.
- Nao ampliar suporte de marketplace apenas adicionando copy, regex ou metadata visual.
- Manter erros semanticos estruturados para o consumidor classificar retry, backoff e status.
