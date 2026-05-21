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

## Identificadores herdados em portugues

Identificadores privados preexistentes em portugues (ex: `_calcular_status`, `_liberar_lease`,
`_fmt_preco`, `_montar_mensagem`) sao aceitos ate que uma refatoracao motivada por outro
criterio objetivo (ADR 0005) justifique a renomeacao. Codigo novo segue a regra de ingles.
