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
})

# Remapeamento de hosts conhecidos por redirecionamento agressivo para o host canônico.
# Aplicado antes da normalização para garantir que a mesma URL de produto tenha
# sempre a mesma forma normalizada, independente de qual host foi informado.
_HOST_REMAP: dict[str, str] = {
    "produto.mercadolivre.com.br": "www.mercadolivre.com.br",
}


_ML_JM_RE = re.compile(r"_JM$", re.IGNORECASE)
_ML_ITEM_ID_RE = re.compile(r"MLB-?(\d+)", re.IGNORECASE)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    netloc = _HOST_REMAP.get(netloc, netloc)

    # URLs publicitárias do ML (_JM) → URL canônica /p/MLB{ID}
    if _ML_JM_RE.search(parsed.path) and "mercadolivre.com.br" in netloc:
        m = _ML_ITEM_ID_RE.search(parsed.path)
        if m:
            return f"https://{netloc}/p/MLB{m.group(1)}"

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
