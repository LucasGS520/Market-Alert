# Contrato Scraper v1

Versao: 1.0  
Proprietario logico: `backend/market_scraper`  
Consumidores: `backend/market_alert/app/infra/clients/scraper.py` e services de coleta.

## Endpoint

`POST {SCRAPER_URL}/scraper/parse`

Request:

```json
{
  "url": "https://www.mercadolivre.com.br/produto"
}
```

## Sucesso

Status: `200 OK`

Campos principais:

```json
{
  "marketplace": "mercadolivre",
  "url": "https://www.mercadolivre.com.br/produto",
  "canonical_url": "https://www.mercadolivre.com.br/produto-canonico",
  "title": "Nome do produto",
  "price": "123.45",
  "currency": "BRL",
  "available": true,
  "seller": "Loja",
  "product_id": "MLB...",
  "thumbnail_url": "https://...",
  "extraction_method": "hydration_json",
  "confidence": 0.95,
  "collected_at": "2026-05-21T12:00:00Z"
}
```

Regra de preco:

- `available=true`: `price` deve existir e ser maior que zero.
- `available=false`: `price` deve ser `null`.

## Erro semantico

Status: `422 Unprocessable Entity`

```json
{
  "detail": {
    "error_code": "MARKETPLACE_NOT_SUPPORTED",
    "marketplace": "unknown",
    "url": "https://example.com/produto",
    "retryable": false,
    "message": "Marketplace nao suportado. Suportado: mercadolivre"
  }
}
```

Codigos oficiais:

- `PRICE_NOT_FOUND`
- `CAPTCHA_DETECTED`
- `BLOCKED`
- `UNAVAILABLE`
- `REDIRECT_TO_SEARCH`
- `LAYOUT_CHANGED`
- `TIMEOUT`
- `MARKETPLACE_NOT_SUPPORTED`

## Timeout e indisponibilidade

- Timeout interno do scraper retorna `504` com `error_code=TIMEOUT` e `retryable=true`.
- Browser ainda inicializando retorna `503` com `error_code=SCRAPER_NOT_READY`.
- Erros HTTP inesperados ou conexao recusada sao classificados no consumidor como indisponibilidade do scraper.

## Marketplace suportado

Mercado Livre e o unico marketplace oficialmente suportado:

- `mercadolivre.com.br`
- `mercadolibre.com`

Adicionar outro marketplace exige adapter validado, testes manuais minimos, contrato atualizado e ADR nova.
