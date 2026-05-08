# pip install selenium webdriver-manager beautifulsoup4

import time
import json
import re
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager


URLS = [
    "https://www.mercadolivre.com.br/protetor-vinilico-soleira-porta-fiat-toro-2-pecas-50927869-/up/MLBU2004182135#polycard_client=recommendations_home_navigation-recommendations&reco_backend=machinalis-homes-univb-equivalent-offer&reco_client=home_navigation-recommendations&reco_item_pos=1&reco_backend_type=function&reco_id=a3db8bec-1751-460d-9b05-06f27739f52d&wid=MLB1161376403&sid=recos&c_id=/home/navigation-recommendations/element&c_uid=6e682181-f5ed-4d63-8abb-55c724cc1fa2",
]


def create_driver(headless=False):
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=pt-BR")

    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    driver.set_page_load_timeout(45)
    return driver


def wait_basic_load(driver):
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )


def extract_json_ld(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for tag in soup.select('script[type="application/ld+json"]'):
        content = tag.get_text(strip=True)

        if not content:
            continue

        try:
            parsed = json.loads(content)
            results.append(parsed)
        except Exception:
            continue

    return results


def extract_meta_data(html):
    soup = BeautifulSoup(html, "html.parser")

    def meta(selector):
        tag = soup.select_one(selector)
        return tag.get("content") if tag and tag.has_attr("content") else None

    title = (
        meta('meta[property="og:title"]')
        or meta('meta[name="title"]')
        or (soup.title.get_text(strip=True) if soup.title else None)
    )

    return {
        "title": title,
        "description": meta('meta[name="description"]'),
        "image": meta('meta[property="og:image"]'),
        "canonical": soup.select_one('link[rel="canonical"]')["href"]
        if soup.select_one('link[rel="canonical"]')
        else None,
    }


def extract_visible_text_signals(driver):
    text = driver.find_element(By.TAG_NAME, "body").text

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


def scrape_url(driver, url):
    print(f"\nAcessando: {url}")

    driver.get(url)
    wait_basic_load(driver)

    # Pequena espera para JS/renderização assíncrona
    time.sleep(5)

    html = driver.page_source

    result = {
        "url": url,
        "final_url": driver.current_url,
        "page_title": driver.title,
        "meta": extract_meta_data(html),
        "json_ld": extract_json_ld(html),
        "signals": extract_visible_text_signals(driver),
    }

    return result


def main():
    driver = create_driver(headless=False)

    try:
        for url in URLS:
            try:
                data = scrape_url(driver, url)

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

            except Exception as e:
                print(f"Erro ao processar URL: {e}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()