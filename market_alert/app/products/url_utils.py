from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "utm_id",
    "fbclid", "gclid", "gad_source", "gad_campaignid",
    "ref", "from", "refid",
})


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    qs = {
        k: v
        for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
        if k not in _TRACKING_PARAMS
    }
    normalized = parsed._replace(
        netloc=parsed.netloc.lower(),
        path=parsed.path.rstrip("/") or "/",
        query=urlencode(qs, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)
