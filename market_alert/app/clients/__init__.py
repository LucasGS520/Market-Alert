"""
Pacote clients — clientes HTTP para serviços externos.

Cada módulo aqui é responsável por comunicar com um serviço externo
específico. Não contêm lógica de negócio — apenas fazem a chamada HTTP
e tratam erros de comunicação.

Módulos disponíveis:
    scraper  → market_scraper (microserviço local de scraping)
    ntfy     → ntfy.sh (push notifications)
    telert   → telert.dev (alertas via token)
"""
