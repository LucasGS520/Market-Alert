# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Sobre o Projeto *Market Alert*

**Objetivo:** monitorar preços de produtos em e-commerce, comparar com concorrentes e enviar alertas quando houver variação relevante.

**Serviços:**
- `backend/market_alert/` — API principal (FastAPI, porta 8000): CRUD de produtos monitorados, concorrentes, histórico e comparações. Orquestra workers Celery.
- `backend/market_scraper/` — Microserviço de scraping (FastAPI, porta 8001): extrai preço/nome/disponibilidade via Playwright + curl-cffi. Stateless.

---

## Comandos de Desenvolvimento

### Docker (recomendado para rodar tudo junto)
```bash
docker compose up              # sobe todos os serviços
docker compose up --build      # reconstrói imagens antes de subir
docker compose logs -f         # acompanha logs
docker compose down            # derruba serviços
```

### Localmente (dentro de backend/market_alert/ ou backend/market_scraper/)
```bash
# API principal
uvicorn app.main:app --reload --port 8000

# Microserviço scraper
uvicorn app.main:app --reload --port 8001

# Workers Celery (executar na raiz de backend/market_alert/)
celery -A app.workers.celery_app worker --queues=collection --concurrency=2
celery -A app.workers.celery_app worker --queues=comparison,default --concurrency=4
celery -A app.workers.celery_app beat

# Migrations (usa DATABASE_SYNC_URL do .env)
alembic upgrade head
alembic revision --autogenerate -m "description"
```

### Lint / Formatação
```bash
ruff check .        # verifica lint
ruff check . --fix  # corrige automaticamente
ruff format .       # formata o código
```

---

## Arquitetura

### Fluxo principal
1. **Beat** dispara `scheduler_task` (fila `default`) a cada minuto.
2. `scheduler_task` enfileira `collector_task` (fila `collection`) para cada produto monitorado.
3. `collector_task` chama `market_scraper` via HTTP → salva preço em `price_history`.
4. Ao salvar preço, enfileira `comparison_task` (fila `comparison`).
5. `comparison_task` calcula delta vs. concorrentes → se `delta >= NOTIFICATION_DELTA_PERCENT` e fora do cooldown, dispara alerta (ntfy / telert).

### Separação de filas Celery
| Fila | Worker | Tarefas |
|------|--------|---------|
| `collection` | collection_worker (concurrency=2) | `collector_task` — I/O pesado (HTTP + scraping) |
| `comparison` | comparison_worker (concurrency=4) | `comparison_task` — cálculos rápidos |
| `default` | comparison_worker (concurrency=4) | `scheduler_task` — leve, roda pelo Beat |

### Redis — 3 bancos separados
- **DB 0** (`REDIS_URL`) — cache, locks, rate limits, cooldowns de domínio/notificação
- **DB 1** (`CELERY_BROKER_URL`) — broker de mensagens Celery
- **DB 2** (`CELERY_RESULT_BACKEND`) — resultados de tasks Celery

### market_scraper — padrão Adapter por marketplace
`router.py` detecta o marketplace pela URL e retorna o adapter correto. Cada adapter em `adapters/` implementa `MarketplaceAdapter` (base.py) para extrair dados daquele site. Marketplace oficial: `mercadolivre` (único com adapter validado — ver ADR 0002).

### Camadas de backend/market_alert/app/
```
api/v1/        → endpoints HTTP finos: valida entrada, chama serviços, retorna schemas
products/      → domínio de produto: monitored/, competitor/, price_history/
comparison/    → cálculo e persistência de snapshots competitivos
notifications/ → detecção de eventos, envio via ntfy e log de tentativas
scheduling/    → política de agendamento e lease de coleta
workers/       → tasks Celery, orquestrador de rodada, coordenação Redis
infra/         → config, database, clients externos (scraper, ntfy)
```

### Variáveis de negócio importantes (`.env`)
- `NOTIFICATION_DELTA_PERCENT` — variação mínima (%) para disparar alerta
- `NOTIFICATION_COOLDOWN_MINUTES` — cooldown entre alertas do mesmo produto
- `DOMAIN_CAPTCHA_COOLDOWN_SECONDS` — cooldown após CAPTCHA detectado pelo scraper

### Governança documental
A fonte de verdade para decisões arquiteturais, contratos e operação está em `docs/`:
- `docs/architecture/adr/` — decisões arquiteturais (ADRs 0001–0005)
- `docs/contracts/` — contratos versionáveis (API v1, scraper, workers, estado, notificações)
- `docs/operations/runbook.md` — diagnóstico de coleta, comparação e ausência de notificação
- `docs/architecture/glossary.md` — nomes canônicos de entidades, estados e eventos

---

## Regras Obrigatórias de Contexto (NÃO IGNORAR)

1. **NÃO liste** árvore inteira do projeto (`tree`, `ls -R`, etc.). Liste apenas pastas-alvo.
2. **NÃO leia** arquivos completos. Leia no máximo 120 linhas por arquivo ou trechos específicos. Se precisar de mais contexto, pergunte antes.
3. **Priorize busca** (`rg`/`grep`) para localizar pontos de mudança antes de abrir arquivos.
4. **Não cole conteúdo integral** de arquivos na resposta. Mostre apenas: arquivos alterados, resumo do diff (o que mudou e por quê), comandos executados e resultados.
5. **Execute somente UMA FASE por vez.** Ao terminar, pare e peça autorização para a próxima.
6. Se detectar duplicação ou overreach fora do escopo, interrompa e reporte.
