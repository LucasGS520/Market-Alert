import httpx
import structlog

logger = structlog.get_logger()

_TELERT_API = "https://telert.dev/api/messages"


async def send_telert(token: str, message: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                _TELERT_API,
                json={"message": message},
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            logger.info("telert_enviado")
        except Exception as exc:
            logger.warning("telert_falhou", erro=str(exc))
