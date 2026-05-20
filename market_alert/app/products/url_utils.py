import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

_TRACKING_PARAMS = frozenset({
    # Universal
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "utm_id",
    "fbclid", "gclid", "gad_source", "gad_campaignid", "msclkid",
    "ref", "from", "refid",
    # Mercado Livre — recomendações e analytics interno
    "reco_backend", "reco_client", "reco_item_pos", "reco_backend_type",
    "reco_id", "reco_model",
    "wid", "sid", "c_id", "c_uid",
    "da_id", "da_position", "da_sort_algorithm", "id_origin",
    # Mercado Livre — publicidade
    "is_advertising", "ad_domain", "ad_position", "ad_click_id",
    "polycard_client", "ads",
    # Mercado Livre — filtros de recomendação (não fazem parte da identidade do produto)
    "pdp_filters",
})

_ML_REJECTED_SUBDOMAIN = re.compile(r"^produto\.mercadolivre\.com\.br$", re.IGNORECASE)
_ML_DOMAIN = re.compile(r"mercadolivre\.com\.br|mercadolibre\.com", re.IGNORECASE)
_ML_PRODUCT_PATH = re.compile(r"/up/MLBU\d+", re.IGNORECASE)
_ML_SHORTLINK_PATH = re.compile(r"/p/MLB", re.IGNORECASE)
_ML_JM_SUFFIX = re.compile(r"_JM(\b|$)", re.IGNORECASE)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()

    qs = {
        k: v
        for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
        if k not in _TRACKING_PARAMS
    }
    normalized = parsed._replace(
        netloc=netloc,
        path=parsed.path.rstrip("/") or "/",
        query=urlencode(qs, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def is_valid_product_url(url: str) -> bool:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path

    if not _ML_DOMAIN.search(netloc):
        return False

    if _ML_REJECTED_SUBDOMAIN.match(netloc):
        return False

    if _ML_SHORTLINK_PATH.search(path):
        return False

    if _ML_JM_SUFFIX.search(path):
        return False

    return bool(_ML_PRODUCT_PATH.search(path))


def get_url_rejection_reason(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path

    if not _ML_DOMAIN.search(netloc):
        return (
            "Marketplace não suportado. "
            "Apenas Mercado Livre (www.mercadolivre.com.br) é suportado atualmente."
        )

    if _ML_REJECTED_SUBDOMAIN.match(netloc):
        return (
            "O domínio 'produto.mercadolivre.com.br' não é suportado. "
            "Abra o produto no Mercado Livre e copie a URL de 'www.mercadolivre.com.br'."
        )

    if _ML_SHORTLINK_PATH.search(path):
        return (
            "URL de atalho detectada (/p/MLB...). "
            "Acesse o produto e copie a URL completa contendo '/up/MLBU...'."
        )

    if _ML_JM_SUFFIX.search(path):
        return (
            "URL de recomendação detectada (sufixo _JM). "
            "Acesse o produto diretamente e copie a URL completa contendo '/up/MLBU...'."
        )

    return (
        "URL do Mercado Livre inválida. "
        "Use a URL direta do produto no formato 'www.mercadolivre.com.br/.../up/MLBU...'."
    )


_RESOLVE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}


async def resolve_canonical_url(url: str, timeout: float = 8.0) -> str | None:
    """Segue redirects HTTP para obter a URL canônica do produto.

    Útil para URLs de recomendação (produto.mercadolivre.com.br/_JM) e
    shortlinks (/p/MLB...) que redirecionam para a URL canônica /up/MLBU...
    Retorna a URL normalizada após o redirect, ou None em caso de falha.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=_RESOLVE_HEADERS,
        ) as client:
            resp = await client.head(normalize_url(url))
            return normalize_url(str(resp.url))
    except Exception:
        return None
