# ADR 0004: Comentarios em PT-BR e Identificadores em Ingles

Status: Aceita  
Data: 2026-05-21

## Contexto

O codigo usa identificadores em ingles e comentarios/docstrings em portugues em varios pontos. A falta de regra explicita pode gerar mistura inconsistente.

## Decisao

Identificadores de codigo permanecem em ingles. Comentarios explicativos e docstrings publicas podem ser em PT-BR. Termos tecnicos mantem o nome original em ingles na primeira mencao.

## Consequencias

- Nao duplicar o mesmo comentario em dois idiomas.
- Comentarios devem explicar intencao, restricao ou decisao nao obvia.
- Comentarios que repetem a linha de codigo devem ser evitados ou removidos.
