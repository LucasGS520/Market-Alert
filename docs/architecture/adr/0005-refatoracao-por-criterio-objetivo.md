# ADR 0005: Refatoracao por Criterio Objetivo

Status: Aceita  
Data: 2026-05-21

## Contexto

O objetivo da etapa e organizar sem alterar comportamento. Reorganizacoes cosmeticas aumentam risco e podem esconder regressao.

## Decisao

Mover ou refatorar arquivos somente quando houver ambiguidade real, responsabilidade em dominio errado, dependencia circular, reducao clara de navegacao contextual e equivalencia de comportamento.

## Consequencias

- Nenhum arquivo deve ser movido apenas por estetica.
- Toda movimentacao deve atualizar imports, README do servico e documentacao central.
- Quando houver duvida, preservar a estrutura atual e documentar a decisao.
