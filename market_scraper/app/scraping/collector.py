import asyncio
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import structlog

from app.core.config import settings

_HTTP_MAX_RETRIES = 2
_HTTP_RETRY_BACKOFF_S = 2.0

logger = structlog.get_logger()

# Parâmetros de rastreamento/publicidade que não afetam o conteúdo do produto.
# Removidos antes de qualquer fetch (HTTP ou browser) para reduzir sinais de bot.
_STRIP_PARAMS = frozenset({
    # Mercado Livre — recomendações internas
    "reco_backend", "reco_client", "reco_item_pos", "reco_backend_type",
    "reco_id", "reco_model",
    # Mercado Livre — analytics interno
    "wid", "sid", "c_id", "c_uid",
    "da_id", "da_position", "da_sort_algorithm", "id_origin",
    # Mercado Livre — publicidade
    "is_advertising", "ad_domain", "ad_position", "ad_click_id",
    "polycard_client",
    # Magalu
    "ads",
    # Universal
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "fbclid", "gclid", "msclkid",
})


def clean_url(url: str) -> str:
    """
    Remove o fragment (#...) e parâmetros de rastreamento da URL,
    preservando apenas o que é relevante para identificar o produto.
    """
    parsed = urlparse(url)
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        clean_qs = {k: v for k, v in qs.items() if k not in _STRIP_PARAMS}
        clean_query = urlencode(clean_qs, doseq=True)
    else:
        clean_query = ""
    return urlunparse(parsed._replace(query=clean_query, fragment=""))


class CollectionError(Exception):
    """Erro ao tentar buscar o HTML de uma URL (HTTP ou Playwright)."""
    pass


async def fetch_with_http(url: str) -> str:
    """
    Baixa o HTML de uma URL usando curl_cffi com fingerprint do Chrome.

    Raises:
        CollectionError: em caso de erro HTTP 4xx/5xx ou falha de rede.
    """
    from curl_cffi.requests import AsyncSession

    url_clean = clean_url(url)
    async with AsyncSession(impersonate="chrome124") as session:
        for attempt in range(_HTTP_MAX_RETRIES + 1):
            response = await session.get(
                url_clean,
                timeout=settings.request_timeout_seconds,
                headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"},
                allow_redirects=True,
            )
            if response.status_code == 429 and attempt < _HTTP_MAX_RETRIES:
                wait = float(response.headers.get("Retry-After", _HTTP_RETRY_BACKOFF_S))
                logger.info("http_429_aguardando_retry", url=url_clean, attempt=attempt + 1, wait_s=wait)
                await asyncio.sleep(wait)
                continue
            if response.status_code == 403:
                raise CollectionError(f"HTTP 403 ao acessar {url_clean} — acesso bloqueado")
            if response.status_code >= 400:
                raise CollectionError(f"HTTP {response.status_code} ao acessar {url_clean}")
            return response.text
        raise CollectionError(f"HTTP 429 persistente após {_HTTP_MAX_RETRIES} tentativas: {url_clean}")
