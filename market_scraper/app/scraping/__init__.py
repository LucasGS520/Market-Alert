"""
Pacote scraping — coleta e extração de dados de páginas web.

Módulos:
    collector → faz a requisição HTTP e retorna o HTML bruto
    parser    → extrai preço, disponibilidade e nome do HTML

Separação de responsabilidades:
    O collector não sabe nada sobre o formato do HTML — apenas o busca.
    O parser não faz requisições — apenas processa o HTML recebido.
    O main.py orquestra os dois chamando collect_and_parse().
"""
