# ADR 0002: Mercado Livre como Marketplace Oficial

Status: Aceita  
Data: 2026-05-21

## Contexto

O router do scraper possui adapter validado para Mercado Livre. Outros marketplaces nao possuem adapter oficial nem contrato validado.

## Decisao

Mercado Livre e o unico marketplace oficialmente suportado ate existir adapter validado, contrato atualizado e ADR nova.

## Consequencias

- UI, docs e mensagens nao devem prometer suporte funcional a outros marketplaces.
- URLs fora do Mercado Livre devem ser tratadas como nao suportadas.
- Compatibilidades visuais historicas nao ampliam suporte oficial.
