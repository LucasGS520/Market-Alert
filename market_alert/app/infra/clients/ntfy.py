import unicodedata

import httpx
import structlog

logger = structlog.get_logger()


def _ascii_header(value: str) -> str:
    """Normaliza para ASCII: remove acentos, descarta caracteres não mapeáveis."""
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").strip()


async def send_ntfy(url: str, topic: str, title: str, message: str) -> None:
    endpoint = f"{url.rstrip('/')}/{topic}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            endpoint,
            content=message.encode(),
            headers={
                "Title": _ascii_header(title),
                "Priority": "default",
                "Tags": "chart_with_upwards_trend",
            },
        )
        response.raise_for_status()
        logger.info("ntfy_enviado", topico=topic, titulo=title)
