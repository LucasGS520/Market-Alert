import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

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

_ML_DOMAIN = re.compile(r"mercadolivre\.com\.br|mercadolibre\.com", re.IGNORECASE)
_NON_PRODUCT_PATH = re.compile(
    r"^/(search|listado|loja|cart|checkout|login|gz|identity|security|c/)",
    re.IGNORECASE,
)


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

    if _NON_PRODUCT_PATH.match(path):
        return False

    return True


def get_url_rejection_reason(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path

    if not _ML_DOMAIN.search(netloc):
        return (
            "Marketplace não suportado. "
            "Apenas Mercado Livre (mercadolivre.com.br) é suportado atualmente."
        )

    if _NON_PRODUCT_PATH.match(path):
        return (
            "A URL aponta para uma página de busca, categoria ou área não relacionada a produto. "
            "Use a URL direta da página do produto."
        )

    return "URL inválida. Verifique se a URL é de um produto do Mercado Livre."


