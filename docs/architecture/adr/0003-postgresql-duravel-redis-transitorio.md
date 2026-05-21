# ADR 0003: PostgreSQL Duravel e Redis Transitorio

Status: Aceita  
Data: 2026-05-21

## Contexto

O sistema usa PostgreSQL para entidades e historico, enquanto Redis coordena Celery, locks, leases, cooldowns, caches e rodadas.

## Decisao

PostgreSQL guarda fatos duraveis. Redis guarda estado operacional transitorio.

## Consequencias

- Historico de negocio deve ir para PostgreSQL.
- Perder Redis pode afetar execucao em andamento, mas nao deve apagar a verdade historica.
- Novos dados precisam ser classificados antes da implementacao.
