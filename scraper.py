"""Myntra scraper interface for the dashboard (lazy imports)."""

__all__ = [
    "get_scraper_class",
    "detect_search_mode",
    "normalize_myntra_url",
    "run_name_search_scrape",
    "run_url_scrape",
]


def _load():
    from src.scrapper.enhanced_scraper import (
        MyntraEnhancedScraper,
        detect_search_mode,
        normalize_myntra_url,
    )
    return MyntraEnhancedScraper, detect_search_mode, normalize_myntra_url


def get_scraper_class():
    return _load()[0]


def detect_search_mode(query):
    return _load()[1](query)


def normalize_myntra_url(url):
    return _load()[2](url)


def run_url_scrape(scraper, product_url, max_reviews=30):
    normalized = normalize_myntra_url(product_url)
    return scraper.scrape_product_by_url(normalized, max_reviews=max_reviews)


def run_name_search_scrape(scraper, query, product_count=3):
    if not scraper.search_products(query):
        raise ConnectionError("Could not reach Myntra.")
    products = scraper.extract_products_from_search(product_count=product_count)
    if not products:
        raise ValueError(f"No products found for '{query}'.")
    return products
