import httpx
import structlog

logger = structlog.get_logger()


async def send_ntfy(url: str, topic: str, title: str, message: str) -> None:
    endpoint = f"{url.rstrip('/')}/{topic}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                endpoint,
                content=message.encode(),
                headers={
                    "Title": title,
                    "Priority": "default",
                    "Tags": "chart_with_upwards_trend",
                },
            )
            response.raise_for_status()
            logger.info("ntfy_enviado", topico=topic, titulo=title)
        except Exception as exc:
            logger.warning("ntfy_falhou", topico=topic, erro=str(exc))
