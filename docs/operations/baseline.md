# Baseline Funcional

Versao: 1.0  
Data de referencia: 2026-05-21  
Objetivo: congelar o comportamento atual antes de organizacoes documentais ou estruturais.

## Estado do repositorio

No momento da implementacao desta organizacao:

```text
git status --short
```

Resultado observado: sem alteracoes pendentes antes da criacao desta camada documental.

## Docker Compose

Comando de referencia:

```powershell
docker compose ps
```

Resultado observado no ambiente atual: Docker Desktop/Linux engine nao estava acessivel pelo pipe `dockerDesktopLinuxEngine`.

Isso nao altera o baseline funcional esperado. Significa apenas que a validacao de containers nao pode ser executada neste ambiente naquele momento.

Servicos esperados quando Docker estiver ativo:

- `postgres`
- `redis`
- `market_scraper`
- `market_alert_api`
- `market_alert_migrate`
- `market_alert_collection_worker`
- `market_alert_comparison_worker`
- `market_alert_notification_worker`
- `market_alert_beat`
- `frontend`

## Health checks esperados

- `GET http://localhost:8000/health`: API pronta, banco acessivel e schema aplicado.
- `GET http://localhost:8001/live`: processo do scraper vivo.
- `GET http://localhost:8001/ready`: browser pronto para scraping.
- `GET http://localhost:3000`: frontend servido por Nginx.

## Comandos de validacao

Dentro de `market_alert/`:

```powershell
python -c "import app.main; import app.workers.tasks"
pytest
alembic upgrade head
```

Observacao: `pytest` so e aplicavel quando o diretorio `tests` existir ou testes forem adicionados.

## Comportamento E2E congelado

- Cadastro de produto retorna `202 Accepted`.
- Primeira coleta e enfileirada de forma assincrona.
- Scheduler usa lease para evitar enfileiramento duplicado.
- Coleta principal chama `market_scraper`.
- Mercado Livre e extraido por adapter dedicado.
- Preco coletado atualiza produto e historico.
- Concorrentes sao coletados em rodada coordenada quando aplicavel.
- Comparacao persiste snapshot competitivo.
- Notificacao so e enviada quando regras de alerta, quorum, cooldown e deduplicacao permitem.
- Frontend reflete estado por leituras posteriores da API.

## Criterio de equivalencia depois da organizacao

A organizacao e aceita se:

- Nenhum endpoint foi removido ou renomeado.
- Nenhum schema publico foi alterado.
- Nenhuma migration foi adicionada por motivo documental.
- Nenhuma regra de coleta, comparacao ou notificacao foi alterada.
- Nenhum marketplace novo foi declarado como oficialmente suportado.
- A documentacao explica o comportamento existente sem exigir reescrita.
