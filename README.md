# Market Alert

Market Alert e uma plataforma local de monitoramento e comparacao de precos. A arquitetura atual deve ser preservada: o frontend consulta a API, a API persiste e agenda trabalho, os workers executam processamento assincrono, e o `market_scraper` extrai dados do Mercado Livre.

## Mapa de documentacao

- [Fluxo E2E oficial](docs/architecture/e2e-flow.md)
- [Glossario e nomes canonicos](docs/architecture/glossary.md)
- [Contratos versionaveis](docs/contracts)

Documentacao por servico:

- [frontend](frontend/README.md): UI estatica, contrato de carregamento e telas.
- [market_alert](backend/market_alert/README.md): API, dominio, workers, scheduler, Redis, PostgreSQL e notificacoes.
- [market_scraper](backend/market_scraper/README.md): scraping, adapters, Playwright e contrato `/scraper/parse`.

## Fronteiras oficiais

- `frontend`: interface estatica servida por Nginx, sem bundler ou build step.
- `backend/market_alert`: backend principal com FastAPI, dominio, persistencia e workers Celery.
- `backend/market_scraper`: microservico de extracao de dados de marketplace.

Mercado Livre e o unico marketplace oficialmente suportado ate o momento.

## Regra de estado

- PostgreSQL guarda fatos duraveis: produtos, concorrentes, historico, comparacoes, logs de notificacao e migrations.
- Redis guarda estado operacional transitorio: broker/result backend Celery, locks, leases, cooldowns, rodadas coordenadas, caches e tentativas recentes.

Nenhum dado necessario para reconstituir historico de negocio deve depender apenas de Redis.

---

## Operacao local

Ambiente oficial:

```powershell
docker compose up --build
```

Servicos esperados:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- Scraper: `http://localhost:8001`
- PostgreSQL: porta `5432`
- Redis: porta `6379`

Validacoes principais:

```powershell
docker compose ps
```

```powershell
cd backend/market_alert
python -c "import app.main; import app.workers.tasks"
pytest
alembic upgrade head
```
