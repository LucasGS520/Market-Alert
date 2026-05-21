# Market Alert

Market Alert e uma plataforma local de monitoramento e comparacao de precos. A arquitetura atual deve ser preservada: o frontend consulta a API, a API persiste e agenda trabalho, os workers executam processamento assincrono, e o `market_scraper` extrai dados do Mercado Livre.

Este README e o ponto oficial de entrada da documentacao. Documentos por servico podem detalhar responsabilidades locais, mas devem permanecer subordinados aos contratos, decisoes e runbooks centralizados em `docs/`.

## Mapa de documentacao

- [Fluxo E2E oficial](docs/architecture/e2e-flow.md)
- [Glossario e nomes canonicos](docs/architecture/glossary.md)
- [Decisoes arquiteturais](docs/architecture/adr)
- [Contratos versionaveis](docs/contracts)
- [Baseline funcional](docs/operations/baseline.md)
- [Runbook operacional](docs/operations/runbook.md)

Documentacao por servico:

- [frontend](frontend/README.md): UI estatica, contrato de carregamento e telas.
- [market_alert](market_alert/README.md): API, dominio, workers, scheduler, Redis, PostgreSQL e notificacoes.
- [market_scraper](market_scraper/README.md): scraping, adapters, Playwright e contrato `/scraper/parse`.

## Fronteiras oficiais

- `frontend`: interface estatica servida por Nginx, sem bundler ou build step.
- `market_alert`: backend principal com FastAPI, dominio, persistencia e workers Celery.
- `market_scraper`: microservico de extracao de dados de marketplace.
- `docs`: fonte de governanca para fluxo, contratos, operacao e decisoes.

Mercado Livre e o unico marketplace oficialmente suportado ate existir adapter validado e ADR especifica.

## Regra de estado

- PostgreSQL guarda fatos duraveis: produtos, concorrentes, historico, comparacoes, logs de notificacao e migrations.
- Redis guarda estado operacional transitorio: broker/result backend Celery, locks, leases, cooldowns, rodadas coordenadas, caches e tentativas recentes.

Nenhum dado necessario para reconstituir historico de negocio deve depender apenas de Redis.

## Regra de organizacao

Organizar nao significa mudar comportamento. Refatore ou mova arquivos somente quando o checklist abaixo for verdadeiro:

- O nome atual causa ambiguidade.
- O arquivo contem responsabilidade de outro dominio.
- Existe dependencia circular ou limite de camada mal posicionado.
- A mudanca reduz navegacao contextual.
- O comportamento permanece igual.

Qualquer movimentacao deve atualizar imports, README do servico e documentacao central na mesma alteracao.

## Convencao de comentarios

- Identificadores de codigo continuam em ingles.
- Comentarios explicativos podem ser em PT-BR.
- Termos tecnicos mantem o nome original em ingles na primeira mencao.
- Nao duplicar o mesmo comentario em dois idiomas.
- Docstrings publicas podem usar portugues com o termo tecnico em ingles entre parenteses.

Comentarios devem explicar intencao, restricao ou regra nao obvia. Comentarios que apenas repetem o codigo devem ser removidos em manutencoes futuras.

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
cd market_alert
python -c "import app.main; import app.workers.tasks"
pytest
alembic upgrade head
```

Health checks:

- `http://localhost:8000/health`
- `http://localhost:8001/live`
- `http://localhost:8001/ready`

## Criterio de pronto para mudancas organizacionais

- README raiz aponta para toda documentacao de governanca.
- Documentacao por servico permanece subordinada ao README raiz.
- Contratos possuem versao, proprietario logico e consumidores.
- Fluxo E2E documentado bate com o runtime observado.
- Runbook explica coleta, comparacao, scheduler, scraper e ausencia de notificacao.
- Nenhum comportamento, endpoint, schema ou marketplace novo foi introduzido apenas por organizacao.
