import aiosmtplib
import structlog
from email.message import EmailMessage

logger = structlog.get_logger()


async def send_email(
    *,
    smtp_host: str,
    smtp_port: int,
    username: str | None,
    password: str | None,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    use_tls: bool = True,
) -> None:
    """Envia e-mail via SMTP assíncrono.

    Compatível com Gmail (STARTTLS, porta 587) e Mailpit local (sem TLS, porta 1025).
    """
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    await aiosmtplib.send(
        msg,
        hostname=smtp_host,
        port=smtp_port,
        username=username or None,
        password=password or None,
        start_tls=use_tls,
    )
    logger.info("email_smtp_enviado", para=to_addr, assunto=subject)
