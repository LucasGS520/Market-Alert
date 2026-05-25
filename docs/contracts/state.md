# Contrato de Estado

Versao: 1.0  
Proprietario logico: `backend/market_alert/app/infra`, `backend/market_alert/app/workers`, migrations Alembic.

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

## Dados de mercado vs. dados da referencia

O modelo distingue dois planos de informacao dentro de um snapshot de comparacao:

### Dados de mercado (sempre calculados quando ha ofertas validas)

Persistidos em `comparisons`. Validos mesmo quando `reference_available == False`.

| Campo | Significado |
|---|---|
| `min_price` | Menor preco entre todas as ofertas validas |
| `max_price` | Maior preco entre todas as ofertas validas |
| `average_price` | Media dos precos validos |
| `participants_count` | Total de ofertas que entraram no calculo |
| `valid_competitors_count` | Concorrentes validos na rodada |
| `ignored_competitors_count` | Concorrentes ignorados (sem preco, inativos) |
| `run_status` | Status da rodada de coleta coordenada |

### Dados da oferta de referencia (condicionais)

Presentes apenas quando `reference_available == True`. Ficam `NULL` quando a referencia esta indisponivel.

| Campo | Significado |
|---|---|
| `status` | Status competitivo da referencia (`competitive`, `attention`, `urgent`) |
| `ranking` | Posicao da referencia entre todas as ofertas |
| `potential_adjustment` | Diferenca para igualar o menor preco |
| `product_price` | Preco da referencia no momento do snapshot |

### Campo de controle

| Campo | Significado |
|---|---|
| `reference_available` | `True` se a oferta de referencia participou do snapshot |

### Dados transientes (Redis)

Estado operacional que nao precisa sobreviver reinicializacao:

- Lease de coleta (`collection_lease_until`).
- Rodada coordenada (`collection_run:{run_id}`).
- Cooldown de notificacao.
- Cache de comparacao.

## Criterio para novos dados

Perguntas obrigatorias:

- O dado precisa ser auditavel depois de dias ou semanas?
- A UI precisa reconstruir historico a partir dele?
- A perda desse dado altera a verdade de negocio?
- O dado precisa participar de relatorio, exportacao ou suporte?

Se qualquer resposta for sim, o dado e duravel e deve ir para PostgreSQL.

Se todas forem nao e o dado existir apenas para coordenar execucao atual, ele pode ir para Redis.
