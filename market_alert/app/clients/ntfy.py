"""
Cliente para o ntfy.sh — serviço de push notification open source.

O ntfy.sh permite receber notificações em qualquer dispositivo via
assinatura de um tópico. Pode ser usado na nuvem (ntfy.sh) ou
auto-hospedado na própria empresa.

Como funciona:
    Um POST HTTP com o texto da mensagem no corpo + headers de título
    e prioridade é suficiente. O servidor ntfy distribui para todos
    os dispositivos assinando aquele tópico.

Documentação: https://docs.ntfy.sh/publish/
"""

import httpx
import structlog

logger = structlog.get_logger()


async def send_ntfy(url: str, topic: str, title: str, message: str) -> None:
    """
    Envia uma notificação push via ntfy.sh.

    Args:
        url:     URL base do servidor ntfy (ex: "https://ntfy.sh").
        topic:   Tópico para publicar (ex: "market_alert").
        title:   Título exibido na notificação.
        message: Texto completo da notificação.

    Não lança exceção em caso de falha — apenas loga o erro para
    não interromper o fluxo de notificação de outros canais.
    """
    endpoint = f"{url.rstrip('/')}/{topic}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                endpoint,
                content=message.encode(),
                headers={
                    "Title": title,       # Título da notificação push
                    "Priority": "default",
                    "Tags": "chart_with_upwards_trend",  # Emoji no ntfy
                },
            )
            response.raise_for_status()
            logger.info("ntfy_enviado", topico=topic, titulo=title)
        except Exception as exc:
            # Falha silenciosa: notificação é best-effort, não deve parar o sistema
            logger.warning("ntfy_falhou", topico=topic, erro=str(exc))
