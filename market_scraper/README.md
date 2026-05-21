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

## Contrato HTTP

Contrato oficial: [docs/contracts/scraper-v1.md](../docs/contracts/scraper-v1.md).

Endpoint:

```text
POST /scraper/parse
```

Request:

```json
{
  "url": "https://www.mercadolivre.com.br/produto"
}
```

Respostas principais:

- `200`: extracao bem-sucedida.
- `422`: erro semantico como `MARKETPLACE_NOT_SUPPORTED` ou `PRICE_NOT_FOUND`.
- `503`: browser ainda nao pronto.
- `504`: timeout global.

## Health checks

- `/live`: processo vivo.
- `/ready`: browser inicializado e pronto.
- `/health`: alias operacional de prontidao.

## Marketplace

Mercado Livre e o unico marketplace oficialmente suportado:

- `mercadolivre.com.br`
- `mercadolibre.com`

Adicionar outro marketplace exige adapter validado, contrato atualizado e ADR nova.

## Regra de manutencao

- Nao acoplar scraping a notificacao ou comparacao.
- Nao persistir estado de negocio no scraper.
- Nao ampliar suporte de marketplace apenas adicionando copy, regex ou metadata visual.
- Manter erros semanticos estruturados para o consumidor classificar retry, backoff e status.
