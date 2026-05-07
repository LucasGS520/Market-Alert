import asyncio
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import structlog
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Response,
    async_playwright,
)

from app.core.config import settings
from app.schemas import CollectedPage
from app.scraping.collector import clean_url
from app.scraping.extractor import detect_captcha

logger = structlog.get_logger()

# Seletores comuns de banner de cookies (tentativa best-effort)
_COOKIE_ACCEPT_SELECTORS = [
    "button:has-text('Aceitar')",
    "button:has-text('Aceitar todos')",
    "button:has-text('Accept')",
    "button:has-text('Accept all')",
    "[id*='cookie'] button[class*='accept']",
    "[class*='cookie'] button[class*='accept']",
    "[data-testid*='cookie-accept']",
]

# Configuração de sessão por marketplace
_SESSION_CONFIG: dict[str, dict[str, Any]] = {
    "mercadolivre": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1280, "height": 800},
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "intercept_patterns": [r"/api/pdp/", r"/pdp/"],
    },
    "shopee": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1280, "height": 800},
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "intercept_patterns": [r"/api/v4/pdp/get_pc", r"/api/v\d+/item/"],
    },
    "magalu": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1280, "height": 800},
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "intercept_patterns": [r"/_next/data/", r"/api/catalog/"],
        # Headers completos de Chrome 131 — Cloudflare valida Sec-Ch-Ua e client hints
        "extra_http_headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        },
    },
}

# Patches de stealth injetados em todos os contextos antes de qualquer script da página.
# Cobre as propriedades mais inspecionadas por sistemas anti-bot (Cloudflare, DataDome).
_STEALTH_SCRIPT = """
// Remove webdriver flag
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Idiomas realistas de pt-BR
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});

// Plugins não-zerados (browsers reais têm plugins)
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});

// chrome object presente (ausente em Playwright puro)
window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};

// Permissions API retorna estado real para notifications (como browser real)
const origQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : origQuery(parameters);
"""


class BrowserSession:
    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContext] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        pw = await async_playwright().start()
        self._pw = pw
        self._browser = await pw.chromium.launch(
            headless=settings.playwright_headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )
        logger.info("browser_iniciado", headless=settings.playwright_headless)

    def _cookie_path(self, marketplace: str) -> Path:
        state_dir = Path(settings.session_state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / f"{marketplace}.json"

    async def _save_context_state(self, marketplace: str) -> None:
        """Persiste cookies e storage do contexto em disco (best-effort)."""
        try:
            ctx = self._contexts.get(marketplace)
            if ctx:
                await ctx.storage_state(path=str(self._cookie_path(marketplace)))
                logger.debug("sessao_salva", marketplace=marketplace)
        except Exception as exc:
            logger.debug("sessao_save_falhou", marketplace=marketplace, erro=str(exc))

    async def _get_context(self, marketplace: str) -> BrowserContext:
        async with self._lock:
            if marketplace not in self._contexts:
                cfg = _SESSION_CONFIG.get(marketplace, _SESSION_CONFIG["mercadolivre"])
                cookie_file = self._cookie_path(marketplace)
                storage_state = str(cookie_file) if cookie_file.exists() else None
                if storage_state:
                    logger.debug("sessao_carregada", marketplace=marketplace)

                ctx = await self._browser.new_context(
                    user_agent=cfg["user_agent"],
                    viewport=cfg["viewport"],
                    locale=cfg["locale"],
                    timezone_id=cfg["timezone_id"],
                    extra_http_headers=cfg.get("extra_http_headers", {}),
                    storage_state=storage_state,
                )
                await ctx.add_init_script(_STEALTH_SCRIPT)
                self._contexts[marketplace] = ctx
                logger.info("contexto_criado", marketplace=marketplace, cookies_restaurados=storage_state is not None)
            return self._contexts[marketplace]

    async def navigate_and_collect(
        self,
        url: str,
        marketplace: str,
        wait_condition: Callable[[Page], Awaitable[None]] | None = None,
        extra_intercept_patterns: list[str] | None = None,
    ) -> CollectedPage:
        url = clean_url(url)

        cfg = _SESSION_CONFIG.get(marketplace, {})
        patterns = list(cfg.get("intercept_patterns", []))
        if extra_intercept_patterns:
            patterns.extend(extra_intercept_patterns)

        context = await self._get_context(marketplace)
        page = await context.new_page()
        captured_payloads: list[dict] = []
        blocked = False
        captcha_detected = False
        status_code: int | None = None
        error: str | None = None

        async def _on_response(response: Response) -> None:
            resp_url = response.url
            if not any(re.search(p, resp_url) for p in patterns):
                return
            if len(captured_payloads) >= settings.max_intercepted_payloads:
                return
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                return
            try:
                body = await response.json()
                captured_payloads.append({"url": resp_url, "body": body})
                logger.debug("payload_capturado", url=resp_url, marketplace=marketplace)
            except Exception:
                pass

        page.on("response", _on_response)

        try:
            resp = await page.goto(
                url,
                timeout=settings.playwright_timeout_ms,
                wait_until="commit",
            )
            if resp:
                status_code = resp.status
                if resp.status == 403:
                    blocked = True
                    logger.warning("browser_403", url=url, marketplace=marketplace)

            if not blocked:
                await _try_accept_cookies(page)

                if wait_condition is not None:
                    await wait_condition(page)
                else:
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=settings.playwright_timeout_ms,
                    )

            html = await page.content()
            captcha_detected = detect_captcha(html)

        except Exception as exc:
            error = str(exc)
            logger.warning("browser_navegacao_falhou", url=url, marketplace=marketplace, erro=error)
            html = None
        finally:
            await page.close()
            await self._save_context_state(marketplace)

        return CollectedPage(
            url=url,
            marketplace=marketplace,
            html=html,
            network_payloads=captured_payloads,
            rendered=True,
            blocked=blocked,
            captcha_detected=captcha_detected,
            status_code=status_code,
            error=error,
        )

    async def close_all(self) -> None:
        for marketplace in list(self._contexts):
            await self._save_context_state(marketplace)
        for ctx in self._contexts.values():
            await ctx.close()
        self._contexts.clear()
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_pw"):
            await self._pw.stop()
        logger.info("browser_encerrado")


async def _try_accept_cookies(page: Page) -> None:
    for selector in _COOKIE_ACCEPT_SELECTORS:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=800):
                await btn.click(timeout=800)
                logger.debug("cookie_aceito", selector=selector)
                return
        except Exception:
            continue
