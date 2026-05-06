"""
Pacote services — lógica de negócio da aplicação.

Aqui ficam as operações que envolvem regras de negócio reais: coleta de preços,
cálculo de comparações, avaliação de alertas e agendamento adaptativo.

Módulos disponíveis:
    collection   → coleta preço de produto ou concorrente via scraper
    comparison   → calcula ranking e status competitivo entre produtos
    notifications → avalia e dispara alertas quando há mudanças de preço
    scheduling   → calcula o intervalo dinâmico entre coletas

Separação de responsabilidades:
    Os services orquestram a lógica usando models (banco) e clients (HTTP).
    Os workers Celery chamam os services de forma assíncrona.
    Os routers da API chamam os services diretamente para operações síncronas.
"""
