"""
Coletor de HTML — responsável por baixar o conteúdo de páginas web.

Estratégia em duas camadas:

    1ª tentativa — HTTP com curl_cffi:
        Rápido (~1-3s). Imita o fingerprint TLS do Chrome real, o que
        passa pela maioria das proteções anti-bot básicas.
        Biblioteca: curl_cffi (wrapper Python do libcurl com fingerprinting)

    2ª tentativa — Playwright (fallback):
        Lança um navegador Chromium headless real. Renderiza JavaScript,
        executa cookies de sessão, espera o carregamento da página.
        Mais lento (~5-15s) e consome ~200MB de RAM por instância.
        Ativado apenas se settings.playwright_enabled = True.

Quando usar qual:
    curl_cffi: ~80% dos e-commerces brasileiros (Mercado Livre, Shopee, etc.)
    Playwright: sites com Cloudflare Bot Management, CAPTCHA ou carregamento via JS
"""

import asyncio
from typing import Literal
from urllib.parse import urldefrag

import structlog

from app.core.config import settings

_HTTP_MAX_RETRIES = 2
_HTTP_RETRY_BACKOFF_S = 2.0

logger = structlog.get_logger()


class CollectionError(Exception):
    """Erro ao tentar buscar o HTML de uma URL (HTTP ou Playwright)."""
    pass


async def fetch_with_http(url: str) -> str:
    """
    Baixa o HTML de uma URL usando curl_cffi com fingerprint do Chrome.

    Args:
        url: URL da página a ser baixada.

    Returns:
        Conteúdo HTML da página como string.

    Raises:
        CollectionError: Se o servidor retornar erro (4xx/5xx) ou houver falha de rede.
    """
    from curl_cffi.requests import AsyncSession

    url_clean, _ = urldefrag(url)
    async with AsyncSession(impersonate="chrome120") as session:
        for attempt in range(_HTTP_MAX_RETRIES + 1):
            response = await session.get(
                url_clean,
                timeout=settings.request_timeout_seconds,
                headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"},
                allow_redirects=True,
            )
            if response.status_code == 429 and attempt < _HTTP_MAX_RETRIES:
                wait = float(response.headers.get("Retry-After", _HTTP_RETRY_BACKOFF_S))
                logger.info("http_429_aguardando_retry", url=url_clean, attempt=attempt + 1, wait_s=wait)
                await asyncio.sleep(wait)
                continue
            if response.status_code == 403:
                logger.warning("coleta_bloqueada_403", url=url_clean, motivo="anti-bot ou IP bloqueado pelo servidor")
                raise CollectionError(f"HTTP 403 ao acessar {url_clean} — acesso bloqueado")
            if response.status_code >= 400:
                raise CollectionError(f"HTTP {response.status_code} ao acessar {url_clean}")
            return response.text
        raise CollectionError(f"HTTP 429 persistente após {_HTTP_MAX_RETRIES} tentativas: {url_clean}")


async def fetch_with_playwright(url: str) -> str:
    """
    Baixa o HTML usando um navegador Chromium headless real.

    Útil para páginas que exigem JavaScript ou têm proteção anti-bot avançada.

    Args:
        url: URL da página a ser carregada.

    Returns:
        HTML completo da página após carregamento (incluindo conteúdo dinâmico).

    Raises:
        CollectionError: Se o Playwright não conseguir carregar a página.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(headless=True)
        except Exception as exc:
            raise CollectionError(f"Playwright não conseguiu iniciar o browser: {exc}") from exc
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="pt-BR",
        )
        page = await context.new_page()
        try:
            await page.goto(url, timeout=settings.playwright_timeout_ms, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle", timeout=settings.playwright_timeout_ms)
            return await page.content()
        except Exception as exc:
            raise CollectionError(f"Playwright falhou para {url}: {exc}") from exc
        finally:
            await browser.close()


async def fetch_html(url: str) -> tuple[str, Literal["http", "playwright"]]:
    """
    Busca o HTML de uma URL tentando HTTP primeiro e Playwright como fallback.

    Args:
        url: URL da página a ser coletada.

    Returns:
        Tupla (html, método_usado) onde método é "http" ou "playwright".

    Raises:
        CollectionError: Se ambas as estratégias falharem.
    """
    try:
        html = await fetch_with_http(url)
        logger.debug("coleta_http_sucesso", url=url)
        return html, "http"
    except CollectionError as exc:
        if not settings.playwright_enabled:
            logger.info("playwright_desabilitado_sem_fallback", url=url, motivo=str(exc))
            raise
        logger.info("http_falhou_tentando_playwright", url=url, motivo=str(exc))

    # Tenta Playwright como fallback
    try:
        html = await fetch_with_playwright(url)
    except CollectionError:
        raise
    except Exception as exc:
        raise CollectionError(f"Playwright erro inesperado para {url}: {exc}") from exc
    logger.debug("coleta_playwright_sucesso", url=url)
    return html, "playwright"
