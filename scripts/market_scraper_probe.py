#!/usr/bin/env python
"""Probe de scraping alinhado ao fluxo do market_scraper.

O script roda os mesmos adapters usados pelo serviço FastAPI e imprime
um diagnóstico separado por etapa:
- roteamento do marketplace
- coleta da página (HTTP/browser/payloads)
- extração final (sucesso ou erro semântico)

Por padrão ele usa o pipeline direto do módulo, porque isso mostra melhor
onde a URL quebra: bloqueio, captcha, layout ou ausência de preço.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRAPER_DIR = ROOT_DIR / "market_scraper"

for path in (ROOT_DIR, SCRAPER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

_router_module = importlib.import_module("app.router")
_schemas_module = importlib.import_module("app.schemas")
_browser_module = importlib.import_module("app.scraping.browser")

MarketplaceRouter = _router_module.MarketplaceRouter
ScrapeError = _schemas_module.ScrapeError
ScrapeResult = _schemas_module.ScrapeResult
BrowserSession = _browser_module.BrowserSession

DEFAULT_URLS = [
    "https://produto.mercadolivre.com.br/MLB-2674274038-farol-fiat-uno-2004-2005-2006-2007-2008-09-mascara-negra-_JM#reco_item_pos=1&reco_backend=item_decorator&reco_backend_type=function&reco_client=home_items-decorator-legacy&reco_id=5231b856-51ad-42bb-b4a9-8da764f3dbfe&reco_model=&c_id=/home/navigation-trends-recommendations/element&c_uid=fffcbc84-0de9-48d4-a694-e60edc34f550&da_id=navigation_trend&da_position=2&id_origin=/home/dynamic_access&da_sort_algorithm=ranker",
    "https://produto.mercadolivre.com.br/MLB-4103190781-refletor-lanterna-parachoque-traseiro-hb20-2023-2024-2025-_JM?searchVariation=184000131856&pdp_filters=seller_id%3A193163363#polycard_client=search-desktop&be_origin=backend&searchVariation=184000131856&search_layout=grid&position=11&type=item&tracking_id=316ca3e2-7e56-4580-889d-47946efeb50e",
]

DEFAULT_API_URL = "http://127.0.0.1:8001/scraper/parse"


class DiagnosisReport:
    """Relatório de diagnóstico com análise de causa raiz e recomendações."""

    def __init__(self, output_dir: Path = Path(".probe_results")) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results: list[dict[str, Any]] = []
        self.timestamp = datetime.now().isoformat()

    def add_result(
        self,
        url: str,
        marketplace: str,
        collected: Any,
        extraction: ScrapeResult | ScrapeError,
        elapsed_seconds: float,
    ) -> None:
        """Registra um resultado de URL com análise de diagnóstico."""
        is_success = isinstance(extraction, ScrapeResult)
        error_code = None if is_success else extraction.error_code.value

        diagnosis = self._analyze_failure(collected, extraction, marketplace)

        self.results.append({
            "url": url,
            "marketplace": marketplace,
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed_seconds,
            "success": is_success,
            "error_code": error_code,
            "collection": {
                "final_url": collected.final_url,
                "status_code": collected.status_code,
                "blocked": collected.blocked,
                "captcha_detected": collected.captcha_detected,
                "html_length": len(collected.html) if collected.html else 0,
                "payload_count": len(collected.network_payloads),
                "error": collected.error,
            },
            "extraction": extraction.model_dump(mode="json") if is_success else error_code,
            "diagnosis": diagnosis,
        })

    def _analyze_failure(
        self,
        collected: Any,
        extraction: ScrapeResult | ScrapeError,
        marketplace: str,
    ) -> dict[str, Any]:
        """Análise de causa raiz de falhas."""
        if isinstance(extraction, ScrapeResult):
            return {"status": "success", "cause": None, "recommendations": []}

        cause = None
        recommendations = []

        # Detectar bloqueio (HTTP 403 ou BLOCKED flag)
        if collected.blocked or collected.status_code == 403:
            cause = "BLOQUEIO_ANTI_BOT"
            recommendations = [
                "Mercado Livre detecta Playwright via inspeção de comportamento",
                "Stealth script cobre webdriver mas não comportamento de rede",
            ]

        # Detectar CAPTCHA
        elif collected.captcha_detected:
            cause = "CAPTCHA_DETECTADO"
            recommendations = [
                f"CAPTCHA detectado no HTML de {marketplace}",
                "IP/sessão foi marcado como suspeito",
                "Solução: aguardar DOMAIN_CAPTCHA_COOLDOWN_SECONDS antes de retry",
                "Implementação: usar Redis para marcar domínios bloqueados por CAPTCHA",
            ]

        # Detectar PRICE_NOT_FOUND (layout ou extração)
        elif extraction.error_code.value == "PRICE_NOT_FOUND":
            if collected.html is None:
                cause = "HTML_NAO_COLETADO"
                recommendations = [
                    "Navegação falhou ou HTML não foi capturado",
                    "Possível timeout durante wait_condition",
                    "Solução: aumentar timeout, usar wait condition mais robusta",
                ]
            elif collected.status_code == 403:
                cause = "BLOQUEIO_NAO_DETECTADO_EM_COLETA"
                recommendations = [
                    "HTTP 403 recebido mas não marcado como bloqueado",
                    "Possível bug em BrowserSession.navigate_and_collect",
                ]
            else:
                cause = "FALHA_EXTRACAO_SELETORES"
                recommendations = [
                    "Seletores CSS desatualizados para novo layout React",
                    f"HTML coletado ({collected.html and len(collected.html)} bytes)",
                    "Solução: mapear novo layout com inspetor do navegador",
                    "Alternativa: extrair via JSON-LD (schema.org) se disponível",
                ]

        # Detectar redirecionamento para busca/categoria
        elif extraction.error_code.value == "REDIRECT_TO_SEARCH":
            cause = "REDIRECIONAMENTO_PARA_BUSCA"
            recommendations = [
                f"URL original: {collected.url}",
                f"URL final: {collected.final_url}",
                "URL redirecionou para página de busca ou categoria, não de produto",
                "Verifique se a URL é de um produto individual",
            ]

        return {
            "status": "failed",
            "cause": cause,
            "recommendations": recommendations,
        }

    def save_json(self) -> Path:
        """Salva resultados em JSON com timestamp."""
        filename = f"probe_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": self.timestamp,
                "total_results": len(self.results),
                "results": self.results,
            }, f, ensure_ascii=False, indent=2, default=_json_default)
        return filepath

    def print_summary(self) -> None:
        """Imprime resumo consolidado por marketplace."""
        if not self.results:
            print("\nNenhum resultado para resumir.")
            return

        by_marketplace = {}
        for result in self.results:
            mp = result["marketplace"]
            if mp not in by_marketplace:
                by_marketplace[mp] = {"success": 0, "failed": 0, "errors": {}, "times": []}
            if result["success"]:
                by_marketplace[mp]["success"] += 1
            else:
                by_marketplace[mp]["failed"] += 1
                error = result["error_code"]
                by_marketplace[mp]["errors"][error] = by_marketplace[mp]["errors"].get(error, 0) + 1
            by_marketplace[mp]["times"].append(result["elapsed_seconds"])

        print("\n" + "=" * 80)
        print("RESUMO DE DIAGNÓSTICO POR MARKETPLACE")
        print("=" * 80)

        for marketplace, stats in sorted(by_marketplace.items()):
            total = stats["success"] + stats["failed"]
            success_rate = (stats["success"] / total * 100) if total > 0 else 0
            avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0

            print(f"\n📊 {marketplace.upper()}")
            print(f"   Taxa de sucesso: {stats['success']}/{total} ({success_rate:.1f}%)")
            print(f"   Tempo médio: {avg_time:.1f}s")

            if stats["errors"]:
                print("   Erros encontrados:")
                for error_code, count in sorted(stats["errors"].items(), key=lambda x: -x[1]):
                    print(f"     - {error_code}: {count}x")


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _pretty_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)


def _normalize_result(result: ScrapeResult | ScrapeError) -> dict[str, Any]:
    payload = result.model_dump(mode="json")
    if isinstance(result, ScrapeResult):
        payload["result_type"] = "success"
    else:
        payload["result_type"] = "error"
        payload["diagnostic"] = _error_diagnostic(result)
    return payload


def _error_diagnostic(error: ScrapeError) -> str:
    if error.error_code.value in {"CAPTCHA_DETECTED", "BLOCKED"}:
        return "anti-bot"
    if error.error_code.value == "REDIRECT_TO_SEARCH":
        return "redirect-to-search-or-category"
    if error.error_code.value == "PRICE_NOT_FOUND":
        return "layout-or-extraction-failure"
    if error.error_code.value == "UNAVAILABLE":
        return "product-not-found-or-unavailable"
    return "unknown"


def _build_collection_summary(collected: Any) -> dict[str, Any]:
    html = collected.html or ""
    return {
        "url": collected.url,
        "marketplace": collected.marketplace,
        "final_url": collected.final_url,
        "status_code": collected.status_code,
        "blocked": collected.blocked,
        "captcha_detected": collected.captcha_detected,
        "rendered": collected.rendered,
        "html_present": collected.html is not None,
        "html_length": len(html),
        "payload_count": len(collected.network_payloads),
        "error": collected.error,
        "collection_diagnostic": (
            "anti-bot"
            if collected.blocked or collected.captcha_detected
            else "html-collected"
            if collected.html
            else "collection-failed"
        ),
    }


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = response.status
            raw = response.read().decode("utf-8")
            return status, json.loads(raw)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            data = json.loads(raw) if raw else {"detail": raw}
        except json.JSONDecodeError:
            data = {"detail": raw or str(exc)}
        return exc.code, data
    except URLError as exc:
        raise RuntimeError(f"Falha ao chamar o endpoint {url}: {exc.reason}") from exc


async def _run_direct(urls: list[str], delay_seconds: float) -> None:
    settings_module = importlib.import_module("app.core.config")
    settings = settings_module.settings

    router = MarketplaceRouter()
    browser = BrowserSession()
    settings.playwright_headless = False
    await browser.start()

    report = DiagnosisReport()

    try:
        for index, url in enumerate(urls, start=1):
            start_time = time.time()
            marketplace = router.detect(url)
            print(f"\n[{index}/{len(urls)}] URL: {url}")
            print(f"Marketplace detectado: {marketplace or 'unknown'}")
            print("Navegação: abrindo janela visível e iniciando coleta")

            if marketplace is None:
                print(_pretty_json({
                    "step": "routing",
                    "result_type": "error",
                    "error_code": "MARKETPLACE_NOT_SUPPORTED",
                    "message": "Marketplace não suportado pelo roteador",
                }))
                if delay_seconds:
                    await asyncio.sleep(delay_seconds)
                continue

            adapter = router.get_adapter(marketplace, browser)
            print(f"Navegação: coletando com adapter '{marketplace}'")
            collected = await adapter.collect(url)
            print(f"Navegação final: {collected.final_url or collected.url}")
            print("Navegação: iniciando extração")
            extraction = await adapter.extract(collected)
            elapsed = time.time() - start_time

            report.add_result(url, marketplace, collected, extraction, elapsed)

            print("Coleta:")
            print(_pretty_json(_build_collection_summary(collected)))
            print("Extração:")
            print(_pretty_json(_normalize_result(extraction)))
            print(f"Tempo de execução: {elapsed:.1f}s")

            if delay_seconds:
                await asyncio.sleep(delay_seconds)
    finally:
        await browser.close_all()

        # Salvar e exibir relatório
        json_path = report.save_json()
        print(f"\n✅ Resultados salvos em: {json_path}")
        report.print_summary()


def _run_api(urls: list[str], api_url: str, timeout_seconds: int) -> None:
    router = MarketplaceRouter()

    for index, url in enumerate(urls, start=1):
        marketplace = router.detect(url)
        print(f"\n[{index}/{len(urls)}] URL: {url}")
        print(f"Marketplace detectado: {marketplace or 'unknown'}")

        try:
            status, data = _post_json(api_url, {"url": url}, timeout_seconds)
        except RuntimeError as exc:
            print(_pretty_json({
                "step": "api",
                "result_type": "error",
                "message": str(exc),
            }))
            continue

        print(_pretty_json({
            "step": "api",
            "http_status": status,
            "response": data,
        }))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa probes alinhados ao market_scraper e imprime um diagnóstico por URL.",
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="URLs de produto a testar. Se omitido, usa os exemplos dos logs.",
    )
    parser.add_argument(
        "--mode",
        choices=("direct", "api"),
        default="direct",
        help="direct usa os adapters do módulo; api chama o endpoint FastAPI local.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="URL do endpoint /scraper/parse quando --mode api estiver ativo.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout em segundos para a chamada HTTP no modo api.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=8.0,
        help="Pausa entre URLs no modo direct, para evitar martelar o mesmo domínio.",
    )
    parser.add_argument(
        "--output-dir",
        default=".probe_results",
        help="Diretório para salvar resultados JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    urls = args.urls or DEFAULT_URLS

    print("Modo:", args.mode)
    print("Total de URLs:", len(urls))
    print(f"Output: {args.output_dir}")

    if args.mode == "api":
        _run_api(urls, args.api_url, args.timeout)
        return

    asyncio.run(_run_direct(urls, args.delay))


if __name__ == "__main__":
    main()