"""
Enhanced Scraper - Scrapes Myntra products using embedded page JSON + Selenium
"""
import json
import re
import traceback
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from src.analytics.product_analytics import ProductAnalytics
from src.analytics.sentiment_analysis import SentimentAnalyzer
from src.config.logger import logger


def detect_search_mode(query):
    """Return 'url' for Myntra links, otherwise 'name'."""
    value = (query or "").strip()
    if re.match(r"^(https?://|www\.)", value, re.IGNORECASE):
        return "url"
    return "name"


def normalize_myntra_url(url):
    """Normalize and validate a Myntra product URL."""
    value = (url or "").strip()
    if not value:
        raise ValueError("Product URL is required.")

    if value.lower().startswith("www."):
        value = f"https://{value}"
    elif not re.match(r"^https?://", value, re.IGNORECASE):
        value = f"https://{value}"

    parsed = urlparse(value)
    host = (parsed.netloc or "").lower()
    if "myntra.com" not in host:
        raise ValueError("Please enter a valid Myntra product URL (myntra.com).")

    path = parsed.path.rstrip("/")
    if not path or path == "/":
        raise ValueError("Invalid product URL. Paste a direct Myntra product page link.")

    return f"https://{host}{path}"


class MyntraEnhancedScraper:
    """Enhanced scraper for Myntra products and reviews."""

    def __init__(self):
        self.base_url = "https://www.myntra.com"
        self.driver = None
        self.sentiment_analyzer = SentimentAnalyzer()
        self.wait_timeout = 15
        self._search_products_cache = []

    def initialize_driver(self):
        """Initialize Selenium WebDriver."""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--window-size=1920,1080")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info("[OK] Chrome WebDriver initialized")
            return self.driver
        except Exception as exc:
            logger.error(f"[ERROR] Error initializing WebDriver: {exc}")
            raise RuntimeError(
                "Unable to start the browser. Please ensure Chrome is installed."
            ) from exc

    def _build_search_url(self, search_query):
        """Build Myntra search URL for any query."""
        query = search_query.strip()
        slug = re.sub(r"\s+", "-", query.lower())
        return f"{self.base_url}/{slug}?rawQuery={quote(query)}"

    def _wait_for_page(self, condition=None):
        """Wait for page content using WebDriverWait."""
        wait = WebDriverWait(self.driver, self.wait_timeout)
        if condition:
            wait.until(condition)
        else:
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

    def _parse_myx_json(self, page_source):
        """Extract window.__myx JSON embedded in Myntra pages."""
        match = re.search(r"window\.__myx\s*=\s*(\{.+?\});?\s*<", page_source, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            logger.warning(f"[WARNING] Failed to parse __myx JSON: {exc}")
            return {}

    def _normalize_product_url(self, landing_page_url):
        """Convert landingPageUrl to absolute product URL."""
        if not landing_page_url:
            return ""
        if landing_page_url.startswith("http"):
            return landing_page_url.split("?")[0]
        path = landing_page_url if landing_page_url.startswith("/") else f"/{landing_page_url}"
        return f"{self.base_url}{path.split('?')[0]}"

    def _map_search_product(self, item):
        """Map Myntra search JSON product to internal schema."""
        brand = item.get("brand") or ProductAnalytics.extract_brand_from_name(
            item.get("productName", "")
        )
        current_price = float(item.get("price") or 0)
        original_price = float(item.get("mrp") or current_price)
        discount_amount = float(item.get("discount") or 0)
        discount_pct = ProductAnalytics.calculate_discount(original_price, current_price)
        if discount_pct == 0 and original_price and discount_amount:
            discount_pct = round((discount_amount / original_price) * 100, 2)

        product_name = item.get("productName") or item.get("product") or "N/A"
        landing_url = item.get("landingPageUrl", "")
        category = (
            item.get("category")
            or item.get("articleType")
            or item.get("subCategory")
            or "N/A"
        )
        image_url = item.get("searchImage") or ""
        if image_url.startswith("http://"):
            image_url = "https://" + image_url[len("http://") :]

        return {
            "product_name": product_name,
            "brand_name": brand,
            "current_price": current_price,
            "original_price": original_price,
            "discount_percentage": discount_pct,
            "product_image_url": image_url,
            "product_category": category,
            "product_url": self._normalize_product_url(landing_url),
            "rating": round(float(item.get("rating") or 0), 2),
            "total_reviews": int(item.get("ratingCount") or 0),
            "product_id": item.get("productId"),
        }

    def search_products(self, search_query):
        """Search for products on Myntra."""
        try:
            search_url = self._build_search_url(search_query)
            logger.info(f"[INFO] Navigating to: {search_url}")
            self.driver.get(search_url)
            self._wait_for_page(
                EC.presence_of_element_located((By.CSS_SELECTOR, "main.search-base, .product-base"))
            )
            logger.info(f"[OK] Searching for: {search_query}")
            return True
        except Exception as exc:
            logger.error(f"[ERROR] Error searching products: {exc}")
            return False

    def extract_products_from_search(self, product_count=50):
        """Extract product summaries from search results page."""
        limit = min(max(int(product_count or 50), 1), 50)
        try:
            page_source = self.driver.page_source
            myx_data = self._parse_myx_json(page_source)
            raw_products = (
                myx_data.get("searchData", {}).get("results", {}).get("products", [])
            )

            products = []
            seen_urls = set()

            for item in raw_products:
                mapped = self._map_search_product(item)
                url = mapped.get("product_url")
                if not mapped.get("product_name") or mapped["product_name"] == "N/A":
                    continue
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                products.append(mapped)

            if not products:
                products = self._extract_products_from_html(page_source, seen_urls)

            self._search_products_cache = products
            logger.info(f"[OK] Extracted {len(products)} unique products from search")
            return products[:limit]
        except Exception as exc:
            logger.error(f"[ERROR] Error extracting products: {exc}")
            logger.error(traceback.format_exc())
            return []

    def _extract_products_from_html(self, page_source, seen_urls=None):
        """Fallback HTML extraction when JSON is unavailable."""
        seen_urls = seen_urls or set()
        soup = BeautifulSoup(page_source, "html.parser")
        products = []

        for card in soup.select("li.product-base, div.product-base"):
            try:
                brand_elem = card.select_one(".product-brand")
                name_elem = card.select_one(".product-product")
                if not brand_elem or not name_elem:
                    continue

                brand = brand_elem.get_text(strip=True)
                name = name_elem.get_text(strip=True)
                product_name = f"{brand} {name}".strip()

                price_elem = card.select_one(".product-discountedPrice, .product-price")
                strike_elem = card.select_one(".product-strike")
                current_price = ProductAnalytics.parse_price(price_elem.get_text() if price_elem else "0")
                original_price = ProductAnalytics.parse_price(strike_elem.get_text() if strike_elem else str(current_price))

                link = card.find("a", href=True)
                product_url = ""
                if link:
                    product_url = self._normalize_product_url(link["href"])

                if not product_url or product_url in seen_urls:
                    continue
                seen_urls.add(product_url)

                img = card.select_one("img.img-responsive, img")
                image_url = img.get("src", "") if img else ""

                products.append(
                    {
                        "product_name": product_name,
                        "brand_name": brand,
                        "current_price": current_price,
                        "original_price": original_price or current_price,
                        "discount_percentage": ProductAnalytics.calculate_discount(
                            original_price, current_price
                        ),
                        "product_image_url": image_url,
                        "product_category": "N/A",
                        "product_url": product_url,
                        "rating": 0.0,
                        "total_reviews": 0,
                    }
                )
            except Exception:
                continue

        return products

    def extract_product_list(self, product_count=50):
        """Return unique product URLs from the latest search."""
        products = self.extract_products_from_search(product_count=product_count)
        return [p["product_url"] for p in products if p.get("product_url")]

    def _coerce_price(self, value, fallback=0.0):
        """Parse price values that may be numbers, strings, or nested dicts."""
        if value is None:
            return fallback
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            for key in ("discounted", "price", "value", "mrp", "amount"):
                if key in value and value[key] is not None:
                    return self._coerce_price(value[key], fallback)
            return fallback
        return ProductAnalytics.parse_price(str(value)) or fallback

    def scrape_product_by_url(self, product_url, max_reviews=30):
        """Scrape a single product directly from its Myntra URL."""
        normalized_url = normalize_myntra_url(product_url)
        logger.info(f"[INFO] Direct URL scrape: {normalized_url}")

        self.driver.get(normalized_url)
        self._wait_for_page(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "main.pdp-pdp-container, h1.pdp-title, .pdp-name")
            )
        )

        page_source = self.driver.page_source.lower()
        if "page not found" in self.driver.title.lower() or "page not found" in page_source[:5000]:
            raise ValueError("Product not found. Check the URL and try again.")

        product_details = self.scrape_product_details(normalized_url, skip_navigation=True)
        if not product_details or not product_details.get("product_name") or product_details.get("product_name") == "N/A":
            raise ValueError("Could not extract product details from this URL.")

        reviews = self.scrape_reviews(normalized_url, max_reviews=max_reviews) or []
        product_details["product_url"] = normalized_url
        return product_details, reviews

    def scrape_product_details(self, product_url, cached_product=None, skip_navigation=False):
        """Scrape or enrich product details."""
        if cached_product and cached_product.get("product_name"):
            return dict(cached_product)

        try:
            logger.info(f"[INFO] Scraping product details: {product_url}")
            if not skip_navigation:
                self.driver.get(product_url)
                self._wait_for_page(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "main.pdp-pdp-container, h1.pdp-title"))
                )

            page_source = self.driver.page_source
            myx_data = self._parse_myx_json(page_source)
            pdp = myx_data.get("pdpData", {})

            if pdp:
                brand_info = pdp.get("brand", {})
                brand = brand_info.get("name") if isinstance(brand_info, dict) else brand_info
                current_price = self._coerce_price(pdp.get("price"))
                original_price = self._coerce_price(pdp.get("mrp"), current_price)
                media = pdp.get("media", {}).get("albums", [{}])
                image_url = ""
                if media and media[0].get("images"):
                    image_url = media[0]["images"][0].get("secureSrc") or media[0]["images"][0].get("src", "")

                analytics = pdp.get("ratings", {}) or {}
                rating_raw = analytics.get("averageRating") if isinstance(analytics, dict) else None
                if rating_raw is None:
                    rating_raw = pdp.get("rating")
                rating = self._coerce_price(rating_raw, 0.0)

                review_count_raw = analytics.get("totalCount") if isinstance(analytics, dict) else None
                if review_count_raw is None:
                    review_count_raw = pdp.get("ratingCount")
                review_count = int(self._coerce_price(review_count_raw, 0))

                product_data = {
                    "product_name": pdp.get("name") or "N/A",
                    "product_url": product_url,
                    "brand_name": brand or ProductAnalytics.extract_brand_from_name(pdp.get("name", "")),
                    "current_price": current_price,
                    "original_price": original_price,
                    "discount_percentage": ProductAnalytics.calculate_discount(original_price, current_price),
                    "product_image_url": image_url,
                    "product_category": pdp.get("articleType") or pdp.get("masterCategory") or "N/A",
                    "rating": round(rating, 2),
                    "total_reviews": review_count,
                }
            else:
                soup = BeautifulSoup(page_source, "html.parser")
                product_data = {
                    "product_name": self._extract_product_name(soup),
                    "product_url": product_url,
                    "current_price": self._extract_current_price(soup),
                    "original_price": self._extract_original_price(soup),
                    "product_image_url": self._extract_image_url(soup),
                    "product_category": self._extract_category(soup),
                }
                product_data["brand_name"] = ProductAnalytics.extract_brand_from_name(
                    product_data["product_name"]
                )
                product_data["discount_percentage"] = ProductAnalytics.calculate_discount(
                    product_data["original_price"], product_data["current_price"]
                )
                product_data["rating"] = self._extract_rating(soup)
                product_data["total_reviews"] = self._extract_review_count(soup)

            if not product_data.get("product_name") or product_data["product_name"] == "N/A":
                logger.warning(f"[WARNING] No product name found for {product_url}")
                return {}

            logger.info(f"[OK] Product details extracted: {product_data['product_name']}")
            return product_data
        except Exception as exc:
            logger.error(f"[ERROR] Error scraping product details: {exc}")
            return cached_product or {}

    def _extract_product_name(self, soup):
        elem = soup.find("h1", class_="pdp-title") or soup.find("h1")
        if elem:
            return elem.get_text(strip=True)
        meta = soup.find("meta", {"property": "og:title"})
        if meta:
            content = meta.get("content", "")
            return content.split("|")[0].strip()
        return "N/A"

    def _extract_current_price(self, soup):
        for selector in (".pdp-price", ".pdp-discounted-price", "span.pdp-price"):
            elem = soup.select_one(selector)
            if elem:
                return ProductAnalytics.parse_price(elem.get_text())
        return 0.0

    def _extract_original_price(self, soup):
        elem = soup.select_one(".pdp-mrp-text, .pdp-discount")
        if elem:
            return ProductAnalytics.parse_price(elem.get_text())
        return self._extract_current_price(soup)

    def _extract_image_url(self, soup):
        meta = soup.find("meta", {"property": "og:image"})
        if meta:
            return meta.get("content", "")
        img = soup.select_one(".image-grid-image, img.pdp-image-container")
        return img.get("src", "") if img else ""

    def _extract_category(self, soup):
        crumbs = soup.select(".breadcrumbs-link")
        if len(crumbs) > 2:
            return crumbs[2].get_text(strip=True)
        return "N/A"

    def _extract_rating(self, soup):
        elem = soup.select_one(".index-overallRating div, .index-ratingsCountContainer")
        if elem:
            match = re.search(r"(\d+\.?\d*)", elem.get_text())
            if match:
                return float(match.group(1))
        return 0.0

    def _extract_review_count(self, soup):
        elem = soup.select_one(".index-ratingsCount, .index-ratingsCountContainer")
        if elem:
            match = re.search(r"(\d[\d,]*)", elem.get_text())
            if match:
                return int(match.group(1).replace(",", ""))
        return 0

    def scrape_reviews(self, product_url, max_reviews=30):
        """Scrape product reviews from the product page."""
        try:
            if self.driver.current_url.split("?")[0] != product_url.split("?")[0]:
                self.driver.get(product_url)
                self._wait_for_page()

            logger.info(f"[INFO] Scraping reviews for: {product_url}")

            try:
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".detailed-reviews-userReviewsContainer, .user-review-main")
                    )
                )
            except Exception:
                logger.info("[INFO] Reviews section not immediately visible; scrolling")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            review_items = soup.select(".detailed-reviews-userReviewsContainer")

            if not review_items:
                review_items = soup.select("div.user-review-main")

            reviews = []
            for item in review_items:
                if len(reviews) >= max_reviews:
                    break
                review_data = self._extract_review_data(item)
                if review_data:
                    reviews.append(review_data)

            logger.info(f"[OK] Extracted {len(reviews)} reviews")
            return reviews
        except Exception as exc:
            logger.error(f"[ERROR] Error scraping reviews: {exc}")
            return []

    def _extract_review_data(self, item):
        """Extract individual review data."""
        try:
            rating = 0
            rating_elem = item.select_one(".user-review-starRating, span.user-review-starRating")
            if rating_elem:
                match = re.search(r"(\d)", rating_elem.get_text(strip=True))
                if match:
                    rating = int(match.group(1))

            comment_elem = item.select_one(
                ".user-review-reviewTextWrapper, .user-review-reviewText"
            )
            comment = comment_elem.get_text(strip=True) if comment_elem else ""
            if not comment:
                comment = item.get_text(strip=True)[:500]
            if not comment or len(comment) < 5:
                return None

            name = "Anonymous"
            date = "N/A"
            name_block = item.select_one(".user-review-left")
            if name_block:
                spans = name_block.find_all("span")
                if spans:
                    name = spans[0].get_text(strip=True)
                if len(spans) > 1:
                    date = spans[1].get_text(strip=True)

            sentiment_data = self.sentiment_analyzer.analyze_sentiment(comment)
            return {
                "user_name": name,
                "user_rating": rating if rating > 0 else 3,
                "review_text": comment,
                "review_date": date,
                "sentiment": sentiment_data["sentiment"],
                "sentiment_score": sentiment_data["polarity"],
            }
        except Exception as exc:
            logger.debug(f"[DEBUG] Error extracting review: {exc}")
            return None

    def close(self):
        """Close WebDriver safely."""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                logger.info("[OK] WebDriver closed")
        except Exception as exc:
            logger.error(f"[ERROR] Error closing WebDriver: {exc}")
