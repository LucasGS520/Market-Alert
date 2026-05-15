import unicodedata

import httpx
import structlog

logger = structlog.get_logger()


def _ascii_header(value: str) -> str:
    """Normaliza para ASCII: remove acentos, descarta caracteres não mapeáveis."""
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").strip()


async def send_ntfy(
    url: str,
    topic: str,
    title: str,
    message: str,
    click_url: str | None = None,
    priority: str = "default",
) -> None:
    endpoint = f"{url.rstrip('/')}/{topic}"
    headers: dict[str, str] = {
        "Title": _ascii_header(title),
        "Priority": priority,
        "Tags": "chart_with_downwards_trend",
    }
    if click_url:
        headers["Click"] = click_url
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(endpoint, content=message.encode(), headers=headers)
        response.raise_for_status()
        logger.info("ntfy_enviado", topico=topic, titulo=title)
