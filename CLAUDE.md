# Claude — Contexto e Objetivos

## Sobre o Projeto *Market Alert* (`market_alert`)
**Objetivo:** monitorar preços de produtos em e‑commerce, comparar com concorrentes e enviar alertas quando houver variação relevante.

**Escopo:** API para CRUD/monitoramento, workers assíncronos (Celery) para coleta e cálculos, microserviço `market_scraper` para extrair preços.

### Arquitetura
- **API / App principal**: FastAPI expondo endpoints e dependências.  
- **Microserviço de scraping**: serviço stateless que extrai preço/nome/disponibilidade.  
- **Fila & agendamento**: Celery (broker/result = Redis) com Beat para agendamento periódico.  
- **Persistência**: PostgreSQL via SQLAlchemy assíncrono.  
- **Cache / locks / broker**: Redis para locks, rate limits, cooldowns e broker/result backend.  
- **Orquestração local**: docker-compose.yml define serviços e dependências (postgres, redis, market_scraper, api, worker, beat).

### Modelos de dados principais
- **MonitoredProduct**: representa um produto a ser monitorado.  
- **Competitor**: URLs concorrentes vinculadas a um `MonitoredProduct`.  
- **PriceHistory**: histórico de coletas (um registro por coleta).  
- **Comparison**: snapshot do posicionamento competitivo (ranking, min/max/avg, status).  
- **NotificationLog**: auditoria de notificações (gravado ao enviar alerts).

---

## Regras e Instruções de Execução
**Regras obrigatórias de economia (NÃO IGNORAR)**
1) NÃO liste árvore inteira do projeto (evite `tree`, `ls -R`, etc.). Se precisar, liste apenas pastas-alvo da FASE.
2) NÃO leia arquivos completos. Leia no máximo 120 linhas por arquivo (ou trechos específicos). Se precisar de mais contextualização, peça antes.
3) Priorize busca (rg/grep) para localizar pontos de mudança antes de abrir arquivos.
5) Não cole conteúdo integral de arquivos na resposta. Mostre apenas:
   - arquivos alterados
   - resumo do diff (o que mudou e por quê)
   - comandos executados e resultados
6) Execute somente UMA FASE por vez. Ao terminar a FASE:
   - pare e peça autorização para a próxima FASE
7) Se detectar duplicação/overreach fora do escopo, interrompa e reporte.

### Regras para market_scraper (NÃO IGNORAR)
- **NUNCA** reintroduza adapters por marketplace nem chamadas a APIs de marketplace (ex.: `api.mercadolibre.com`, `shopee.com.br/api/v4`, qualquer endpoint `/api/`).
- O pipeline é genérico: toda URL passa pelas mesmas 4 estratégias em cascata (JSON-LD → CSS → regex → OG). Marketplace é apenas metadado detectado pela URL, não determina estratégia.
- Chame sempre `fetch_html()` (não `fetch_with_http()` diretamente) para que o fallback Playwright seja automático.
- Ao adicionar seletores ou estratégias de parsing, faça-o em `scraping/extractor.py` de forma genérica.
- URLs de regressão validadas ficam em `market_scraper/tests/regression_urls.py`.