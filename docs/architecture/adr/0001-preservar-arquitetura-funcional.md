# ADR 0001: Preservar Arquitetura Funcional Atual

Status: Aceita  
Data: 2026-05-21

## Contexto

O sistema ja opera como pipeline assincrona: frontend consulta, API persiste e agenda, workers processam em background e `market_scraper` extrai dados externos.

## Decisao

Preservar a arquitetura funcional atual. Organizacao documental ou estrutural nao deve alterar regras de negocio, endpoints, schemas, filas ou comportamento de coleta, comparacao e notificacao.

## Consequencias

- Refatoracoes amplas ficam fora desta etapa.
- Mudancas organizacionais precisam provar equivalencia de comportamento.
- A documentacao deve descrever o runtime real, nao uma arquitetura desejada futura.
