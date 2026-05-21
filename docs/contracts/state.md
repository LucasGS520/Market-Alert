# Contrato de Estado

Versao: 1.0  
Proprietario logico: `market_alert/app/infra`, `market_alert/app/workers`, migrations Alembic.

## Decisao

PostgreSQL guarda fatos duraveis. Redis guarda estado operacional transitorio.

Essa regra e arquitetural, nao apenas operacional. Toda mudanca deve classificar previamente o dado como duravel ou transitorio.

## PostgreSQL

Usar PostgreSQL para:

- Produtos monitorados.
- Concorrentes.
- Historico de preco.
- Snapshots de comparacao.
- Tentativas de notificacao.
- Status duravel de entidades.
- Campos de auditoria necessarios para explicar comportamento passado.
- Schema versionado por Alembic.

Nao usar PostgreSQL para:

- Locks de curta duracao.
- Cooldowns.
- Filas.
- Leases transitorios.
- Cache descartavel.

## Redis

Usar Redis para:

- Broker e result backend do Celery.
- Locks distribuidos.
- Lease de coleta.
- Cooldown de notificacao.
- Rodada coordenada.
- Rate limit e circuit breaker de dominio.
- Cache de comparacao.
- Tentativas recentes de coleta para diagnostico leve.

Nao usar Redis como unica fonte para:

- Historico de preco.
- Historico de comparacoes.
- Entrega de notificacao.
- Estado de negocio que precise sobreviver a limpeza de Redis.

## Criterio para novos dados

Perguntas obrigatorias:

- O dado precisa ser auditavel depois de dias ou semanas?
- A UI precisa reconstruir historico a partir dele?
- A perda desse dado altera a verdade de negocio?
- O dado precisa participar de relatorio, exportacao ou suporte?

Se qualquer resposta for sim, o dado e duravel e deve ir para PostgreSQL.

Se todas forem nao e o dado existir apenas para coordenar execucao atual, ele pode ir para Redis.
