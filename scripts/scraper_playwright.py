import json
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


URLS = [
    "https://www.mercadolivre.com.br/protetor-vinilico-soleira-porta-fiat-toro-2-pecas-50927869-/up/MLBU2004182135#polycard_client=recommendations_home_navigation-recommendations&reco_backend=machinalis-homes-univb-equivalent-offer&reco_client=home_navigation-recommendations&reco_item_pos=1&reco_backend_type=function&reco_id=a3db8bec-1751-460d-9b05-06f27739f52d&wid=MLB1161376403&sid=recos&c_id=/home/navigation-recommendations/element&c_uid=6e682181-f5ed-4d63-8abb-55c724cc1fa2",
]


def extract_json_ld(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for tag in soup.select('script[type="application/ld+json"]'):
        content = tag.get_text(strip=True)

        if not content:
            continue

        try:
            results.append(json.loads(content))
        except Exception:
            pass

    return results


def extract_meta_data(html):
    soup = BeautifulSoup(html, "html.parser")

    def meta(selector):
        tag = soup.select_one(selector)
        return tag.get("content") if tag and tag.has_attr("content") else None

    canonical = soup.select_one('link[rel="canonical"]')

    return {
        "title": (
            meta('meta[property="og:title"]')
            or meta('meta[name="title"]')
            or (soup.title.get_text(strip=True) if soup.title else None)
        ),
        "description": meta('meta[name="description"]'),
        "image": meta('meta[property="og:image"]'),
        "canonical": canonical.get("href") if canonical else None,
    }


def extract_visible_text_signals(page):
    text = page.locator("body").inner_text(timeout=15000)

    price_patterns = [
        r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}",
        r"\d{1,3}(?:\.\d{3})*,\d{2}",
    ]

    prices = []
    for pattern in price_patterns:
        prices.extend(re.findall(pattern, text))

    return {
        "visible_text_length": len(text),
        "sample_text": text[:700],
        "prices_found": list(dict.fromkeys(prices))[:10],
    }


def scrape_url(page, url):
    print(f"\nAcessando: {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(5000)

        html = page.content()

        return {
            "url": url,
            "final_url": page.url,
            "page_title": page.title(),
            "meta": extract_meta_data(html),
            "json_ld": extract_json_ld(html),
            "signals": extract_visible_text_signals(page),
        }

    except Exception as e:
        return {
            "url": url,
            "error": str(e),
        }


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-size=1366,768",
            ],
        )

        context = browser.new_context(
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()
        page.set_default_timeout(30000)

        try:
            for url in URLS:
                data = scrape_url(page, url)

                if "error" in data:
                    print("\nErro:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    continue

                print("\nResultado resumido:")
                print(json.dumps({
                    "final_url": data["final_url"],
                    "page_title": data["page_title"],
                    "meta": data["meta"],
                    "prices_found": data["signals"]["prices_found"],
                    "json_ld_count": len(data["json_ld"]),
                    "visible_text_length": data["signals"]["visible_text_length"],
                }, indent=2, ensure_ascii=False))

                time.sleep(10)

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()