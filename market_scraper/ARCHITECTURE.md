# market_scraper — Documento Arquitetural

> Versão: 2026-05-07  
> Serviço: microserviço de extração de preços de produtos em e-commerce  
> Tecnologias centrais: FastAPI · Playwright · curl_cffi · parsel · price_parser · structlog

---

## 1. Propósito e Escopo

O `market_scraper` é um microserviço stateless responsável por uma única operação: receber a URL de um produto e retornar os dados desse produto (preço, título, disponibilidade, vendedor, ID) de forma estruturada.

Ele não armazena histórico, não agenda coletas e não envia alertas — essas responsabilidades pertencem à API principal e aos workers Celery. O scraper só responde a requisições pontuais de coleta.

**Interface pública:** `POST /scraper/parse` com body `{ "url": "..." }`.

---

## 2. Estrutura de Arquivos

```
market_scraper/
├── app/
│   ├── main.py              # Entrypoint FastAPI; lifespan do BrowserSession
│   ├── router.py            # Detecção de marketplace e instanciação de adapter
│   ├── schemas.py           # Contratos de dados (CollectedPage, ScrapeResult, ScrapeError)
│   ├── core/
│   │   └── config.py        # Settings via Pydantic BaseSettings / .env
│   ├── scraping/
│   │   ├── browser.py       # BrowserSession: Playwright, contextos, stealth, interceptação
│   │   ├── collector.py     # fetch_with_http (curl_cffi) + clean_url
│   │   └── extractor.py     # parse_price_string, detect_captcha (utilitários compartilhados)
│   └── adapters/
│       ├── base.py          # MarketplaceAdapter (ABC): collect / extract / scrape
│       ├── shopee.py        # Adapter Shopee
│       ├── mercadolivre.py  # Adapter Mercado Livre
│       └── magalu.py        # Adapter Magazine Luiza
└── scripts/                 # Scripts auxiliares (teste manual, diagnóstico)
```

---

## 3. Camadas do Módulo

O módulo é organizado em seis camadas com responsabilidades bem definidas. Nenhuma camada deve acessar diretamente a camada não adjacente.

```
┌──────────────────────────────────────────────────────────┐
│  1. Entrypoint (main.py)                                 │
│     HTTP in → valida → roteia → chama adapter → HTTP out │
├──────────────────────────────────────────────────────────┤
│  2. Roteamento (router.py)                               │
│     URL → marketplace → adapter correto                  │
├──────────────────────────────────────────────────────────┤
│  3. Adapter (adapters/*.py)                              │
│     Orquestra collect() + extract() por marketplace      │
├──────────────────────────────────────────────────────────┤
│  4. Coleta (scraping/browser.py + collector.py)          │
│     Busca o HTML e payloads de rede sem interpretar      │
├──────────────────────────────────────────────────────────┤
│  5. Extração (adapters/*.py + scraping/extractor.py)     │
│     Interpreta os dados coletados, retorna resultado     │
├──────────────────────────────────────────────────────────┤
│  6. Contratos (schemas.py + core/config.py)              │
│     Tipos, validações e configuração de ambiente         │
└──────────────────────────────────────────────────────────┘
```

### 3.1 Camada 1 — Entrypoint (`main.py`)

- Inicializa o `BrowserSession` no lifespan da aplicação (uma única instância compartilhada).
- Recebe `POST /scraper/parse`, valida a URL, usa `MarketplaceRouter` para obter o adapter correto e chama `adapter.scrape(url)`.
- Devolve `ScrapeResult` (sucesso) ou `ScrapeError` (falha semântica) como JSON.
- Erros inesperados (exceções não capturadas) são logados com `erro_inesperado_parse`.

### 3.2 Camada 2 — Roteamento (`router.py`)

- `MarketplaceRouter.detect(url)` — regex match no domínio da URL para identificar o marketplace.
- `MarketplaceRouter.get_adapter(marketplace, browser)` — importa dinamicamente e instancia o adapter correto, injetando o `BrowserSession` compartilhado.
- Se o marketplace for desconhecido, retorna `ScrapeError(MARKETPLACE_NOT_SUPPORTED)`.

### 3.3 Camada 3 — Adapter (`adapters/*.py`)

Cada adapter implementa a ABC `MarketplaceAdapter`:

```python
class MarketplaceAdapter(ABC):
    marketplace: str          # identificador ("shopee", "magalu", etc.)
    _browser: BrowserSession  # injetado pelo router

    async def collect(self, url: str) -> CollectedPage: ...
    async def extract(self, page: CollectedPage) -> ScrapeResult | ScrapeError: ...
    async def scrape(self, url: str) -> ScrapeResult | ScrapeError:
        page = await self.collect(url)
        return await self.extract(page)
```

**`collect()`** — define a estratégia de coleta específica do marketplace (ex: HTTP primeiro, browser como fallback). Retorna sempre um `CollectedPage` — nunca lança exceção.

**`extract()`** — interpreta o `CollectedPage` sem fazer I/O. Tenta múltiplas estratégias em ordem de confiabilidade, retornando o primeiro resultado válido.

**Princípio central:** `collect()` e `extract()` são independentes. O `extract()` não sabe como os dados foram coletados; o `collect()` não sabe como os dados serão interpretados.

### 3.4 Camada 4 — Coleta

#### `scraping/browser.py` — BrowserSession

Gerencia o browser Playwright e os contextos por marketplace.

**Responsabilidades:**
- Lançar o browser Chromium com flags anti-bot (`--disable-blink-features=AutomationControlled`).
- Criar e reusar contextos de browser isolados por marketplace (`_get_context()`).
- Injetar `_STEALTH_SCRIPT` via `add_init_script` antes de qualquer script da página.
- Interceptar respostas de rede que correspondam a padrões de URL configurados (`_on_response`).
- Persistir e restaurar cookies/localStorage via `storage_state` entre execuções.
- Chamar `clean_url()` antes de qualquer navegação.
- Detectar CAPTCHA via `detect_captcha(html)` após carregar a página.
- Fechar e salvar contextos ordenadamente ao encerrar.

**Estrutura de contexto por marketplace (`_SESSION_CONFIG`):**

Cada entrada define: user-agent, viewport, locale, timezone, padrões de URL a interceptar, e headers HTTP extras (para Magalu: `Sec-Ch-Ua`, `Sec-Ch-Ua-Platform` etc.).

**Stealth JS injetado (antes de qualquer script da página):**

| Propriedade | Por que importa |
|---|---|
| `navigator.webdriver` | Flag primária de detecção de automação |
| `navigator.languages` | Array pt-BR; browsers headless retornam `["en-US"]` |
| `navigator.plugins` | Array não-vazio; headless retorna `[]` |
| `window.chrome` | Ausente no Playwright puro |
| `navigator.permissions.query` | Retorna estado realista para `notifications` |

**Interceptação de payloads:**

Antes de navegar, registra `page.on("response", _on_response)`. O handler captura apenas respostas JSON cujas URLs correspondam a `intercept_patterns` do marketplace — sem bloquear a navegação. Os payloads capturados são acumulados em `captured_payloads` e repassados no `CollectedPage`.

#### `scraping/collector.py` — HTTP direto

- `fetch_with_http(url)` — usa `curl_cffi.AsyncSession(impersonate="chrome124")` para fazer requisições com fingerprint TLS real do Chrome 124, evitando detecção por JA3/JA4.
- Retry automático em HTTP 429 com `Retry-After`.
- Levanta `CollectionError` em 4xx/5xx.
- `clean_url(url)` — remove fragment (`#...`) e ~25 parâmetros de rastreamento conhecidos (UTM, fbclid, gclid, parâmetros internos de ML/Magalu) antes de qualquer fetch.

### 3.5 Camada 5 — Extração

Cada adapter implementa múltiplas estratégias de extração em ordem decrescente de confiabilidade:

| Estratégia | `ExtractionMethod` | Confidence | Quando usar |
|---|---|---|---|
| Payload de rede interceptado | `NETWORK_PAYLOAD` | 1.0 | Payload JSON capturado da API interna |
| SSR state (`__NEXT_DATA__`) | `SSR_STATE` | 0.95 | JSON embutido no HTML pelo servidor |
| Seletores CSS no DOM | `CSS_SELECTOR` | 0.7–0.8 | HTML renderizado pelo browser |
| JSON-LD / meta tags | `HYDRATION_JSON` | — | Fallback para dados estruturados no HTML |

**`scraping/extractor.py`** — utilitários compartilhados:

- `parse_price_string(text)` — usa a biblioteca `price_parser` para normalizar strings de preço em BR e EN para `Decimal` (ex: `"R$ 1.299,90"` → `Decimal("1299.90")`). Usado por todos os adapters no fallback DOM.
- `detect_captcha(html)` — busca strings características de páginas de CAPTCHA (reCAPTCHA, hCaptcha, Cloudflare challenge) no HTML.

### 3.6 Camada 6 — Contratos e Configuração

#### `schemas.py`

**`CollectedPage`** — DTO de saída do `collect()`, entrada do `extract()`:

```python
@dataclass
class CollectedPage:
    url: str
    marketplace: str
    html: str | None              # None se a navegação falhou completamente
    network_payloads: list[dict]  # Payloads JSON interceptados
    rendered: bool                # True = browser; False = HTTP direto
    blocked: bool                 # HTTP 403 detectado
    captcha_detected: bool        # CAPTCHA no HTML
    status_code: int | None
    error: str | None             # Mensagem de erro de navegação, se houver
```

**`ScrapeResult`** — retorno em caso de sucesso:

```python
class ScrapeResult(BaseModel):
    marketplace: str
    url: str
    canonical_url: str | None
    title: str | None
    price: Decimal
    currency: str             # sempre "BRL"
    available: bool
    seller: str | None
    product_id: str | None
    extraction_method: ExtractionMethod
    confidence: float         # 0.0–1.0
    collected_at: datetime    # UTC, gerado automaticamente
```

**`ScrapeError`** — retorno em caso de falha semântica:

```python
class ScrapeError(BaseModel):
    error_code: ErrorCode
    marketplace: str
    url: str
    retryable: bool           # True = caller deve tentar novamente
    message: str
```

**`ErrorCode`** — códigos de erro semânticos:

| Código | Significado | Retryable típico |
|---|---|---|
| `PRICE_NOT_FOUND` | Nenhuma estratégia extraiu preço | True |
| `CAPTCHA_DETECTED` | Página de desafio detectada | True |
| `BLOCKED` | HTTP 403 | True |
| `UNAVAILABLE` | Produto sem estoque | False |
| `REDIRECT` | URL redirecionou para fora do produto | False |
| `LAYOUT_CHANGED` | Seletores não encontraram nada esperado | True |
| `TIMEOUT` | Timeout de navegação | True |
| `MARKETPLACE_NOT_SUPPORTED` | Domínio não reconhecido | False |

#### `core/config.py` — Settings

Configurável via `.env` ou variáveis de ambiente:

| Variável | Padrão | Descrição |
|---|---|---|
| `PLAYWRIGHT_ENABLED` | `True` | Desabilitar para testes sem browser |
| `PLAYWRIGHT_HEADLESS` | `True` | `False` para depuração local (janela visível) |
| `REQUEST_TIMEOUT_SECONDS` | `15` | Timeout para requisições HTTP |
| `PLAYWRIGHT_TIMEOUT_MS` | `30000` | Timeout geral do Playwright (ms) |
| `MAX_INTERCEPTED_PAYLOADS` | `10` | Limite de payloads interceptados por navegação |
| `SESSION_STATE_DIR` | `.session_state` | Diretório para cookies persistidos |
| `LOG_LEVEL` | `INFO` | Nível de log |

---

## 4. Fluxo Completo de uma Requisição

```
POST /scraper/parse { "url": "https://shopee.com.br/produto-i.123.456" }
        │
        ▼
main.py — valida URL
        │
        ▼
MarketplaceRouter.detect(url) → "shopee"
MarketplaceRouter.get_adapter("shopee", browser) → ShopeeAdapter
        │
        ▼
ShopeeAdapter.scrape(url)
        │
        ├─► collect(url)
        │       │
        │       ▼
        │   clean_url(url) — remove tracking params
        │       │
        │       ▼
        │   BrowserSession.navigate_and_collect(url, "shopee", _wait)
        │       │
        │       ├── _get_context("shopee") — cria ou reutiliza contexto
        │       │       └── storage_state restaurado de .session_state/shopee.json (se existir)
        │       │
        │       ├── page.on("response", _on_response) — registra interceptor
        │       │
        │       ├── page.goto(url, wait_until="commit")
        │       │
        │       ├── _try_accept_cookies(page) — best-effort
        │       │
        │       ├── _wait(page) — wait_for_response("/api/v4/pdp/get_pc", timeout=12s)
        │       │       └── fallback: wait_for_load_state("domcontentloaded", 4s)
        │       │
        │       ├── page.content() → html
        │       │
        │       ├── detect_captcha(html) → captcha_detected
        │       │
        │       └── _save_context_state("shopee") — persiste cookies
        │
        │   CollectedPage { html, network_payloads, rendered=True, ... }
        │
        └─► extract(page)
                │
                ├── captcha_detected? → ScrapeError(CAPTCHA_DETECTED)
                ├── blocked? → ScrapeError(BLOCKED)
                │
                ├── _extract_from_payload(network_payloads)
                │       ├── Tenta paths: data.item / data.result.item / data.item_brief / item
                │       ├── Tenta busca recursiva (_deep_find_price_shopee)
                │       └── price, title, available → ScrapeResult (confidence=1.0)  ✓
                │
                ├── html is None? → ScrapeError(PRICE_NOT_FOUND)  [só aqui, após payload]
                │
                └── _extract_from_dom(sel)
                        ├── Seletores CSS Shopee + meta og:price
                        └── parse_price_string(price_text) → ScrapeResult (confidence=0.7)

        ▼
ScrapeResult { marketplace, url, title, price, currency, confidence, ... }
        │
        ▼
HTTP 200 { ... }
```

---

## 5. Comportamento por Marketplace

### 5.1 Shopee

| Aspecto | Detalhe |
|---|---|
| Coleta | Browser Playwright apenas (SPA, sem SSR útil) |
| Wait condition | `wait_for_response("/api/v4/pdp/get_pc", 12s)` → fallback `domcontentloaded` |
| Estratégia primária | Payload da API interna `/api/v4/pdp/get_pc` (JSON interceptado) |
| Estratégia fallback | Seletores CSS no DOM renderizado |
| Formato de preço | Inteiro × 100.000 (ex: `4990000` → R$ 49,90) |
| ID do produto | Extraído da URL via regex: `/i\.(\d+)\.(\d+)/` |
| Disponibilidade | `item.status == 1 AND item.stock > 0` |
| Interceptação | Padrões: `/api/v4/pdp/get_pc`, `/api/v\d+/item/` |

### 5.2 Mercado Livre

| Aspecto | Detalhe |
|---|---|
| Coleta | Browser Playwright |
| Wait condition | Selector com múltiplos targets: `.ui-pdp-title`, `.andes-money-amount__fraction`, `.poly-component__price`, `.ui-pdp-buybox__offers-item` |
| Estratégia primária | Payload da API interna `/api/pdp/` (JSON interceptado) |
| Estratégia secundária | JSON de hydration no HTML |
| Estratégia fallback | Seletores CSS (cobre layout padrão e layout `/up/` poly-*) |
| Interceptação | Padrões: `/api/pdp/`, `/pdp/` |
| Layout alternativo | URLs `/up/MLBU...` usam componentes `poly-*` — cobertos por seletores adicionais |

### 5.3 Magazine Luiza (Magalu)

| Aspecto | Detalhe |
|---|---|
| Coleta | HTTP primeiro (curl_cffi chrome124) → fallback browser se 403/erro |
| Por que HTTP primeiro | Magalu usa Next.js com SSR; HTML contém `__NEXT_DATA__` com preço completo |
| Proteção anti-bot | Cloudflare Bot Management; exige headers `Sec-Ch-Ua` corretos |
| Wait condition | Selector `[data-testid='price-value']` ou `[class*='price']` → fallback `networkidle` |
| Estratégia 1 | `__NEXT_DATA__` (JSON embutido no HTML pelo SSR) — confidence 0.95 |
| Estratégia 2 | Payload de rede `/_next/data/` (se browser foi usado) — confidence 1.0 |
| Estratégia 3 | Seletores CSS DOM — confidence 0.8 |
| Disponibilidade | `__NEXT_DATA__.props.pageProps.product.available` |
| ID do produto | Regex `/p/([A-Z0-9]+)/` na URL |

---

## 6. Estratégia Anti-Bot

O scraper opera com IP residencial, o que já elimina o principal sinal de bot (IP de datacenter). As demais camadas de defesa são:

### 6.1 TLS Fingerprint — `curl_cffi`

Requisições HTTP usam `curl_cffi` com `impersonate="chrome124"`, que reproduz o handshake TLS do Chrome 124 (JA3/JA4 idêntico ao browser real). Detectores baseados em fingerprint TLS (Cloudflare, Akamai) não distinguem do browser real.

> Limitação: versões do `curl_cffi` < 0.7.x suportam até `chrome124`. Usar `chrome131` requer atualização do pacote.

### 6.2 Browser Fingerprint — Stealth JS

Injetado via `context.add_init_script()` antes de qualquer script da página:

```
navigator.webdriver  → undefined (não detectável como Playwright)
navigator.languages  → ['pt-BR', 'pt', 'en-US', 'en']
navigator.plugins    → array não-vazio [1,2,3,4,5]
window.chrome        → objeto completo com runtime, loadTimes, csi, app
permissions.query    → retorna estado real de Notification.permission
```

### 6.3 Headers HTTP realistas

Contexto Magalu inclui headers completos de Chrome 131:
- `Sec-Ch-Ua`, `Sec-Ch-Ua-Mobile`, `Sec-Ch-Ua-Platform`
- `Sec-Fetch-Dest`, `Sec-Fetch-Mode`, `Sec-Fetch-Site`, `Sec-Fetch-User`
- `Accept`, `Accept-Language`, `Cache-Control`

### 6.4 Session Persistence

Cookies e localStorage são persistidos por marketplace em `.session_state/{marketplace}.json` usando `storage_state()` do Playwright. Na próxima execução, o contexto é restaurado — simulando um usuário que já visitou o site antes.

> Efeito: primeira visita com contexto frio pode ser mais lenta ou falhar; visitas subsequentes usam sessão estabelecida e são significativamente mais rápidas.

### 6.5 Limpeza de URL

`clean_url()` remove tracking parameters antes de qualquer fetch, eliminando sinais de automação presentes em URLs copiadas de campanhas de ads ou de sistemas internos dos marketplaces.

### 6.6 Flags do Chromium

```
--no-sandbox
--disable-blink-features=AutomationControlled  ← remove navigator.webdriver no nível C++
--disable-infobars
```

---

## 7. Logging

O módulo usa `structlog` com campos estruturados. Eventos-chave:

| Evento | Nível | Quando |
|---|---|---|
| `browser_iniciado` | INFO | Browser Playwright levantado |
| `contexto_criado` | INFO | Novo contexto por marketplace; indica `cookies_restaurados` |
| `sessao_salva` | DEBUG | Cookies persistidos após navegação |
| `payload_capturado` | DEBUG | Response JSON interceptado |
| `browser_403` | WARNING | HTTP 403 detectado pelo browser |
| `browser_navegacao_falhou` | WARNING | Exceção no page.goto ou wait_condition |
| `magalu_http_falhou` | INFO | HTTP falhou (403/timeout), browser será tentado |
| `magalu_http_erro_infra` | WARNING | Erro de infraestrutura no HTTP (não CollectionError) |
| `shopee_extracao_sucesso` | INFO | Preço extraído com sucesso; inclui `method` e `price` |
| `magalu_extracao_sucesso` | INFO | Preço extraído com sucesso; inclui `method` e `confidence` |
| `ml_extracao_sucesso` | INFO | Preço extraído com sucesso |
| `erro_inesperado_parse` | ERROR | Exceção não capturada em `/scraper/parse` |

---

## 8. O Que o Módulo Não Faz (Intencionalmente)

- **Não persiste dados** — apenas retorna o resultado ao chamador.
- **Não agenda coletas** — agendamento é responsabilidade do Celery Beat na API principal.
- **Não faz retry** — o campo `retryable` no `ScrapeError` sinaliza ao chamador se deve tentar novamente.
- **Não usa proxies** — depende do IP residencial do host; para alta frequência ou múltiplos IPs, o chamador deve gerenciar instâncias separadas.
- **Não valida o produto** — retorna o que encontra na página; não verifica se a URL ainda existe ou se o produto mudou.
- **Não interpreta dados no `collect()`** — o adapter de coleta sempre retorna `CollectedPage` bruto, sem analisar preços ou títulos.

---

## 9. Como Adicionar um Novo Marketplace

1. Criar `market_scraper/app/adapters/{marketplace}.py` implementando `MarketplaceAdapter`.
2. Implementar `collect()` com a estratégia de coleta adequada (HTTP, browser, ou híbrida).
3. Implementar `extract()` com pelo menos uma estratégia; adicionar `confidence` adequada.
4. Adicionar entrada em `_SESSION_CONFIG` em `browser.py` com `user_agent`, `viewport`, `locale`, `timezone_id`, e `intercept_patterns`.
5. Registrar o domínio em `MarketplaceRouter` em `router.py`.
6. Testar com `POST /scraper/parse` e validar os campos do `ScrapeResult`.

---

## 10. Dependências Externas

| Biblioteca | Versão mínima | Função |
|---|---|---|
| `fastapi` | — | Framework HTTP |
| `playwright` | — | Browser automation |
| `curl_cffi` | ≥ 0.6.x | HTTP com TLS fingerprint Chrome |
| `parsel` | — | Seletores CSS/XPath em HTML |
| `price_parser` | — | Normalização de strings de preço |
| `structlog` | — | Logging estruturado |
| `pydantic` | v2 | Validação de schemas |
| `pydantic-settings` | — | Settings via `.env` |

---

## 11. Decisões de Design e Trade-offs

**Por que separar `collect()` e `extract()`?**  
Permite testar extração com HTML salvo em disco sem precisar de browser. Facilita adicionar estratégias de coleta (ex: cache de HTML) sem alterar a lógica de parsing.

**Por que `CollectedPage` nunca levanta exceção?**  
O caller (`scrape()`) sempre recebe algo para processar. Falhas de navegação são capturadas no `error` field. O `extract()` decide como tratar — retornando `ScrapeError` adequado — em vez de propagar exceções que matariam a requisição sem diagnóstico.

**Por que `confidence` em vez de boolean?**  
O chamador pode decidir se aceita um resultado com confidence 0.7 (DOM) ou se prefere repetir a requisição mais tarde esperando um resultado com confidence 1.0 (payload de API).

**Por que `retryable` no `ScrapeError`?**  
CAPTCHA e bloqueio 403 são retryable (o problema pode ser temporário). Produto indisponível não é retryable (a página existe, mas o dado não vai mudar por mecanismo de retry).

**Por que não usar Selenium ou Puppeteer?**  
Playwright oferece `wait_for_response()` nativa para sincronizar com chamadas de API, interceptação de respostas por URL pattern, e `storage_state()` para persistência de sessão — tudo na mesma API.
