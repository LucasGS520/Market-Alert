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
    "https://www.mercadolivre.com.br/celular-samsung-galaxy-a26-5g-256gb-8gb-ram-cmera-de-50mp-ip67-tela-super-amoled-67-nfc-branco/p/MLB47436035",
    "https://www.mercadolivre.com.br/fone-ouvido-bluetooth-54-sem-fio-estojo-de-carregamento-anti-ruido-a-prova-dagua-compativel-com-ios-samsung-galaxy-android-tws-wireless-air-premium-microfone-touch-marca-pro-phone-see/p/MLB58519492#polycard_client=recommendations_home-deals&reco_backend=deals-model-odin&wid=MLB5758097762&reco_client=home-deals&reco_item_pos=4&reco_backend_type=low_level&reco_id=cb5c1687-10a5-4c49-9c57-6cc8ff519983&sid=recos&c_id=/home/promotions-recommendations/element&c_uid=dfc0d1b8-3eba-43da-9e36-e126072ad33f",
    "https://produto.mercadolivre.com.br/MLB-2891662887-kit-soleira-resinada-proteco-4-portas-8-pecas-fiat-toro-_JM#reco_item_pos=0&reco_backend=item_decorator&reco_backend_type=function&reco_client=home_items-decorator-legacy&reco_id=6a03d1e6-735b-4e7c-82a2-f82f61f1b27b&reco_model=&c_id=/home/navigation-recommendations-seed/element&c_uid=c003e687-f5db-4d0c-89eb-2e1ad0bc63d2&da_id=navigation&da_position=1&id_origin=/home/dynamic_access&da_sort_algorithm=ranker",
    "https://www.mercadolivre.com.br/soleira-protetor-porta-resinada-fiat-strada-ultra-2025-2026/up/MLBU3812407091#polycard_client=recommendations_home_navigation-recommendations&reco_backend=machinalis-homes-univb-equivalent-offer&reco_client=home_navigation-recommendations&reco_item_pos=4&reco_backend_type=function&reco_id=3e5a5d46-b59c-4d08-935b-c04c4a229fe1&wid=MLB6325790006&sid=recos&c_id=/home/navigation-recommendations/element&c_uid=b8d42271-0c01-4a59-ac6f-dd46641a4f1b",
    "https://www.mercadolivre.com.br/fone-ouvido-bluetooth-espelho-impermeavel-display-luz-led-sem-fio-compativel-com-celular-xiaomi-samsung-motorola-iphone-touch-wireless-portatil-profissional-anti-ruido-caixa-usb-carregar-visor-digital/p/MLB67692194?pdp_filters=seller_id%3A426308070#polycard_client=recommendations_pdp-seller_items-above&reco_backend=ranker-retsys-same-seller&reco_model=rk_entity_sameseller&reco_client=pdp-seller_items-above&reco_item_pos=1&reco_backend_type=low_level&reco_id=ce9786cf-a667-422c-8a3c-ded5dcaec8b6&wid=MLB6595018896&sid=recos",
    "https://www.mercadolivre.com.br/celular-samsung-galaxy-a17-5g-com-ia-256gb-8gb-ram-cm-de-50mp-tela-de-67-nfc-ip54-cinza/p/MLB54961626#polycard_client=recommendations_home_second-best-navigation-trend-recommendations&reco_backend=machinalis-homes-univb&wid=MLB6593889648&reco_client=home_second-best-navigation-trend-recommendations&reco_item_pos=1&reco_backend_type=function&reco_id=87d4bcca-e939-4ffb-a47a-e1076a953681&sid=recos&c_id=/home/second-best-navigation-trend-recommendations/element&c_uid=e623112d-2c8c-4ade-b1e2-a0360a22017c",
    "https://www.mercadolivre.com.br/notebook-asus-vivobook-15-x1504va-intel-core-i5-1334u-8gb-ram-512gb-ssd-intel-iris-xe-windows-11-home-tela-156-fhd-silver-nj1740w/p/MLB48549236#polycard_client=recommendations_home-deals&reco_backend=deals-model-odin&wid=MLB5356528958&reco_client=home-deals&reco_item_pos=6&reco_backend_type=low_level&reco_id=da57a626-cc3a-45b8-88c4-ff378b0b8edc&sid=recos&c_id=/home/promotions-recommendations/element&c_uid=0ef6e7a7-6f83-4484-9c27-3215fd05aee1",
    "https://www.mercadolivre.com.br/kit-jogo-de-ferramentas-200-pecas-com-maleta-resistente-titanium-platina/p/MLB35153376#polycard_client=recommendations_home-deals&reco_backend=deals-model-odin&wid=MLB6233871348&reco_client=home-deals&reco_item_pos=1&reco_backend_type=low_level&reco_id=031401df-2b3a-4f27-bef9-a8d937cc0a91&sid=recos&c_id=/home/promotions-recommendations/element&c_uid=698a5f59-4ee8-4186-8e7c-2bb3dbfb8630",
    "https://www.mercadolivre.com.br/mesa-portatil-multifuncional-ergonmica-para-sofa-e-cama/p/MLB67646424#polycard_client=recommendations_home_navigation-related-recommendations&reco_backend=recomm_platform_exp_com_org_rfa&wid=MLB6651575654&reco_client=home_navigation-related-recommendations&reco_item_pos=3&reco_backend_type=function&reco_id=5c218eef-5909-4a48-9d01-bb3cdd45f2d8&sid=recos&c_id=/home/navigation-related-recommendations/element&c_uid=7c20f3a6-3816-4e5d-a266-98c6fcfdad90",
    "https://www.mercadolivre.com.br/mesa-portatil-para-laptop-e-escritorio-mecolour-inclui-mouse-pad-e-apoio-para-os-pulsos/p/MLB59433754?pdp_filters=item_id:MLB4275184507#polycard_client=recommendations_pdp-pads-up&wid=MLB4275184507&sid=recos&reco_backend=recomm_platform_base_pads_rfa_MERGE&reco_model=search_recos_backend_merge&reco_client=pdp-pads-up&reco_item_pos=0&reco_backend_type=low_level&reco_id=6d29d72d-671a-4e89-b1f0-a15a1ebb8559&is_advertising=true&ad_domain=PDPDESKTOP_UP&ad_position=1&ad_click_id=MmJhOWQ1YjktNWRiMC00MmFjLWI5OTMtMTkzZjUzMTUzNmM0",
    "https://www.mercadolivre.com.br/kit-adesivo-skin-notebook-dell-inspiron-15-3520/up/MLBU3866209758#polycard_client=recommendations_home_navigation-related-recommendations&reco_backend=recomm_platform_exp_com_org_rfa&reco_client=home_navigation-related-recommendations&reco_item_pos=2&reco_backend_type=function&reco_id=67029004-3a01-4e5b-ae74-3782d3266fbc&wid=MLB4555354243&sid=recos&c_id=/home/navigation-related-recommendations/element&c_uid=86f502bf-caa3-48a2-a070-3957b70cdb8c",
    "https://www.mercadolivre.com.br/chave-tigre-boca-universal-48-em-1-profissional-360-graus/up/MLBU2877191651#polycard_client=recommendations_home_third-best-navigation-trend-recommendations&reco_backend=machinalis-homes-univb&reco_client=home_third-best-navigation-trend-recommendations&reco_item_pos=3&reco_backend_type=function&reco_id=c34e6d0e-487d-4032-b849-9f96fcdd71e3&wid=MLB3924853397&sid=recos&c_id=/home/third-best-navigation-trend-recommendations/element&c_uid=cd65e8a8-8006-4f73-832a-0ca8e1335d6d",
    "https://www.mercadolivre.com.br/kit-jogo-de-alicates-universal-corte-bico-e-presso-4-pcs/p/MLB68983562#polycard_client=recommendations_home_navigation-related-recommendations&reco_backend=recomm_platform_exp_com_org_rfa&wid=MLB6703612652&reco_client=home_navigation-related-recommendations&reco_item_pos=3&reco_backend_type=function&reco_id=ee55a619-534f-462e-bd5f-7fd6573e949b&sid=recos&c_id=/home/navigation-related-recommendations/element&c_uid=d864e221-2149-4a44-b5a7-9598c605ede7",
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

        # Detectar REDIRECT
        elif extraction.error_code.value == "REDIRECT":
            cause = "REDIRECIONAMENTO_NAO_PRODUTO"
            if collected.final_url != collected.url:
                recommendations = [
                    f"URL original: {collected.url}",
                    f"URL final: {collected.final_url}",
                    "Página foi redirecionada para página de busca, home ou erro",
                    "Possível que URL está quebrada, produto foi removido ou URL é de recomendação",
                ]
            else:
                recommendations = [
                    "Página parece ser de busca/recomendação, não de produto único",
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
    if error.error_code.value == "REDIRECT":
        return "redirect-to-non-product-page"
    if error.error_code.value == "PRICE_NOT_FOUND":
        return "layout-or-extraction-failure"
    if error.error_code.value == "UNAVAILABLE":
        return "out-of-stock"
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