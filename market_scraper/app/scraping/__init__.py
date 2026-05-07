"""
Pacote scraping — utilitários de coleta e parsing de páginas web.

    browser    → BrowserSession: contexto Playwright persistente por marketplace
    collector  → fetch_with_http: coleta raw de HTML via curl_cffi (fingerprint Chrome)
    extractor  → parse_price_string / extract_jsonld / detect_captcha: parsing compartilhado
"""
