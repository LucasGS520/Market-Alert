"""
Cliente para o Telert — serviço de alertas via API REST.

O Telert envia mensagens para diferentes canais (Telegram, Slack, etc.)
a partir de um token Bearer. É uma alternativa ao ntfy.sh quando se
prefere integração com apps de mensageria existentes.

Configuração necessária: definir TELERT_TOKEN no .env
Documentação: https://telert.dev
"""

import httpx
import structlog

logger = structlog.get_logger()

# URL da API do Telert (não configurável — é sempre este endpoint)
_TELERT_API = "https://telert.dev/api/messages"


async def send_telert(token: str, message: str) -> None:
    """
    Envia uma mensagem via Telert.

    Args:
        token:   Token Bearer obtido no painel do Telert.
        message: Texto da mensagem a enviar.

    Não lança exceção em caso de falha — apenas loga o erro.
    """
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
            # Falha silenciosa: não deve interromper outros canais de notificação
            logger.warning("telert_falhou", erro=str(exc))
