"""
Pacote scraping — coleta e extração de dados de páginas web.

    collector  → requisição HTTP/Playwright, retorna HTML bruto
    extractor  → pipeline de parsing (JSON-LD → CSS → regex → OG)
"""

from app.scraping.collector import fetch_html
from app.scraping.extractor import extract_product

__all__ = ["fetch_html", "extract_product"]
