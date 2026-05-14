import asyncio
import random
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
}

# Patches de stealth injetados em todos os contextos antes de qualquer script da página.
# Cobre as propriedades mais inspecionadas por sistemas anti-bot (Cloudflare, DataDome).
_STEALTH_SCRIPT = """
// Remove webdriver flag
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Linguagens e vendor
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});
Object.defineProperty(navigator, 'vendor', {get: () => 'Google Inc.'});

// PluginArray realista com objetos Plugin reais (array puro é detectável)
const makePlugin = (name, desc, filename) => {
    const p = Object.create(Plugin.prototype);
    Object.defineProperty(p, 'name', {value: name});
    Object.defineProperty(p, 'description', {value: desc});
    Object.defineProperty(p, 'filename', {value: filename});
    Object.defineProperty(p, 'length', {value: 0});
    return p;
};
const _plugins = [
    makePlugin('PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer'),
    makePlugin('Chrome PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer'),
    makePlugin('Chromium PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer'),
    makePlugin('Microsoft Edge PDF Viewer', 'Portable Document Format', 'internal-pdf-viewer'),
    makePlugin('WebKit built-in PDF', 'Portable Document Format', 'internal-pdf-viewer'),
];
Object.defineProperty(navigator, 'plugins', {
    get: () => Object.assign(_plugins, {
        item: i => _plugins[i],
        namedItem: n => _plugins.find(p => p.name === n) || null,
        refresh: () => {},
        length: _plugins.length,
    }),
});

// navigator.connection — ausente em headless, presente em Chrome real
Object.defineProperty(navigator, 'connection', {
    get: () => ({effectiveType: '4g', rtt: 50, downlink: 10, saveData: false,
                 onchange: null, addEventListener: () => {}, removeEventListener: () => {}}),
});

// Hardware concurrency e device memory
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});

// Dimensões externas — headless retorna 0, browser real tem barra de ferramentas (+88px)
Object.defineProperty(window, 'outerWidth', {get: () => window.innerWidth});
Object.defineProperty(window, 'outerHeight', {get: () => window.innerHeight + 88});

// screen.availHeight — taskbar ocupa ~40px na parte inferior
Object.defineProperty(screen, 'availWidth', {get: () => screen.width});
Object.defineProperty(screen, 'availHeight', {get: () => screen.height - 40});

// chrome object completo com runtime funcional
window.chrome = {
    app: {
        isInstalled: false,
        InstallState: {DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed'},
        RunningState: {CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running'},
    },
    runtime: {
        id: undefined,
        connect: () => ({disconnect: () => {}, onDisconnect: {addListener: () => {}},
                         onMessage: {addListener: () => {}}, postMessage: () => {}}),
        sendMessage: () => {},
        onMessage: {addListener: () => {}},
        onConnect: {addListener: () => {}},
    },
    loadTimes: () => ({firstPaintTime: 0, firstPaintAfterLoadTime: 0, finishDocumentLoadTime: 0}),
    csi: () => ({startE: Date.now(), onloadT: Date.now(), pageT: 0, tran: 15}),
};

// Permissions API — retorna estado real para notifications
const origQuery = window.navigator.permissions.query.bind(window.navigator.permissions);
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : origQuery(parameters);

// WebGL renderer — SwiftShader expõe headless; substituir por Intel realista
try {
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.call(this, parameter);
    };
} catch(e) {}
"""

# Homepages para warm-up de sessão fria — visitar antes do primeiro produto
_MARKETPLACE_HOMEPAGES: dict[str, str] = {
    "mercadolivre": "https://www.mercadolivre.com.br/",
}


def _bezier_points(
    x0: int, y0: int, x1: int, y1: int, steps: int
) -> list[tuple[int, int]]:
    cx = (x0 + x1) // 2 + random.randint(-120, 120)
    cy = (y0 + y1) // 2 + random.randint(-80, 80)
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        x = int((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1)
        y = int((1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1)
        points.append((x, y))
    return points


async def _move_mouse_humanlike(page: Page) -> None:
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        w, h = vp["width"], vp["height"]
        sx = random.randint(10, w // 3)
        sy = random.randint(10, h // 5)
        tx = random.randint(w // 4, 3 * w // 4)
        ty = random.randint(h // 4, 2 * h // 3)
        steps = random.randint(8, 16)
        for x, y in _bezier_points(sx, sy, tx, ty, steps):
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.018, 0.075))
        for _ in range(random.randint(2, 4)):
            await page.mouse.move(
                tx + random.randint(-5, 5),
                ty + random.randint(-5, 5),
            )
            await asyncio.sleep(random.uniform(0.05, 0.15))
    except Exception:
        pass


class BrowserSession:
    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContext] = {}
        self._lock = asyncio.Lock()
        # Serializa navegações por marketplace: impede múltiplas páginas simultâneas
        # no mesmo contexto, evitando que reset por CAPTCHA mate páginas em andamento.
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def is_ready(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def start(self) -> None:
        pw = await async_playwright().start()
        self._pw = pw
        self._browser = await pw.chromium.launch(
            headless=settings.playwright_headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-ipc-flooding-protection",
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

    async def reset_context(self, marketplace: str) -> None:
        """Descarta o contexto envenenado (CAPTCHA/blocked) sem salvar cookies."""
        async with self._lock:
            ctx = self._contexts.pop(marketplace, None)
        if ctx:
            try:
                await ctx.close()
            except Exception as exc:
                logger.debug("contexto_close_falhou", marketplace=marketplace, erro=str(exc))
            logger.info("contexto_resetado", marketplace=marketplace)
        # Remove o arquivo de disco para que a sessão envenenada não seja restaurada
        cookie_file = self._cookie_path(marketplace)
        try:
            cookie_file.unlink(missing_ok=True)
            logger.debug("sessao_disco_removida", marketplace=marketplace)
        except Exception:
            pass

    async def _warm_up_context(self, marketplace: str, ctx: BrowserContext) -> None:
        """Visita a homepage com interações reais antes do primeiro produto."""
        homepage = _MARKETPLACE_HOMEPAGES.get(marketplace)
        if not homepage:
            return
        page = await ctx.new_page()
        try:
            await page.goto(homepage, timeout=20000, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await asyncio.sleep(random.uniform(0.8, 1.8))
            await _move_mouse_humanlike(page)
            for _ in range(random.randint(2, 4)):
                amount = random.randint(120, 300)
                await page.evaluate(
                    f"window.scrollBy({{top: {amount}, behavior: 'smooth'}})"
                )
                await asyncio.sleep(random.uniform(0.6, 1.5))
            await asyncio.sleep(random.uniform(0.5, 1.2))
            logger.info("contexto_aquecido", marketplace=marketplace, homepage=homepage)
        except Exception as exc:
            logger.debug("warm_up_falhou", marketplace=marketplace, erro=str(exc))
        finally:
            await page.close()

    async def _get_context(self, marketplace: str) -> BrowserContext:
        async with self._lock:
            if marketplace not in self._semaphores:
                self._semaphores[marketplace] = asyncio.Semaphore(1)
            if marketplace not in self._contexts:
                cfg = _SESSION_CONFIG.get(marketplace, _SESSION_CONFIG["mercadolivre"])
                cookie_file = self._cookie_path(marketplace)
                storage_state = str(cookie_file) if cookie_file.exists() else None
                if storage_state:
                    logger.debug("sessao_carregada", marketplace=marketplace)

                base_vp = cfg["viewport"]
                viewport = {
                    "width": base_vp["width"] + random.randint(-20, 20),
                    "height": base_vp["height"] + random.randint(-20, 20),
                }
                if self._browser is None:
                    raise RuntimeError("Browser ainda não inicializado")

                ctx = await self._browser.new_context(
                    user_agent=cfg["user_agent"],
                    viewport=viewport,
                    locale=cfg["locale"],
                    timezone_id=cfg["timezone_id"],
                    extra_http_headers=cfg.get("extra_http_headers", {}),
                    storage_state=storage_state,
                )
                await ctx.add_init_script(_STEALTH_SCRIPT)
                self._contexts[marketplace] = ctx
                logger.info("contexto_criado", marketplace=marketplace, cookies_restaurados=storage_state is not None)

                if storage_state is None:
                    await self._warm_up_context(marketplace, ctx)

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

        # Garante que contexto e semáforo existam antes de adquirir o semáforo.
        await self._get_context(marketplace)

        async with self._semaphores[marketplace]:
            # Re-fetch: contexto pode ter sido resetado por chamada anterior.
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
                referrer = _MARKETPLACE_HOMEPAGES.get(marketplace, "")
                if referrer:
                    await page.set_extra_http_headers({"Referer": referrer})

                await asyncio.sleep(random.uniform(0.3, 1.5))

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

                    await _simulate_human_behavior(page)

                html = await page.content()
                captcha_detected = detect_captcha(html)

            except Exception as exc:
                error = str(exc)
                logger.warning("browser_navegacao_falhou", url=url, marketplace=marketplace, erro=error)
                html = None
            finally:
                await page.close()
                # Não persiste cookies quando CAPTCHA detectado — a sessão está envenenada
                cfg_persist = _SESSION_CONFIG.get(marketplace, {})
                should_persist = cfg_persist.get("persist_session", True)
                if not captcha_detected and not blocked and should_persist:
                    await self._save_context_state(marketplace)

            if captcha_detected or blocked:
                await self.reset_context(marketplace)

            return CollectedPage(
                url=url,
                marketplace=marketplace,
                final_url=page.url,
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


async def _simulate_human_behavior(page: Page) -> None:
    try:
        await asyncio.sleep(random.uniform(0.5, 1.2))
        await _move_mouse_humanlike(page)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        total_px = random.randint(450, 950)
        steps = random.randint(3, 6)
        step_px = total_px // steps
        for _ in range(steps):
            amount = step_px + random.randint(-40, 40)
            await page.evaluate(
                f"window.scrollBy({{top: {amount}, behavior: 'smooth'}})"
            )
            await asyncio.sleep(random.uniform(0.7, 2.2))
        if random.random() < 0.30:
            await asyncio.sleep(random.uniform(0.4, 1.0))
            back = random.randint(120, 320)
            await page.evaluate(
                f"window.scrollBy({{top: -{back}, behavior: 'smooth'}})"
            )
            await asyncio.sleep(random.uniform(0.5, 1.2))
        await asyncio.sleep(random.uniform(0.5, 1.0))
    except Exception:
        pass


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
