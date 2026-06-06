"""Analytics engine: charts, sentiment, word cloud, recommendations."""
import base64
import io
from collections import Counter

from src.analytics.product_analytics import ProductAnalytics
from src.analytics.sentiment_analysis import SentimentAnalyzer
from src.recommendation.engine import RecommendationEngine


def _price_bucket(price):
    if price <= 500:
        return "₹0-500"
    if price <= 1000:
        return "₹500-1K"
    if price <= 2000:
        return "₹1K-2K"
    if price <= 5000:
        return "₹2K-5K"
    return "₹5K+"


def build_chart_data(products, reviews=None):
    """Build all chart datasets from products and optional reviews."""
    products = products or []
    reviews = reviews or []

    price_labels = ["₹0-500", "₹500-1K", "₹1K-2K", "₹2K-5K", "₹5K+"]
    price_counts = {label: 0 for label in price_labels}
    brand_counts = Counter()
    brand_prices = {}
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    for p in products:
        bucket = _price_bucket(float(p.get("current_price") or 0))
        price_counts[bucket] = price_counts.get(bucket, 0) + 1

        brand = p.get("brand_name") or "Other"
        brand_counts[brand] += 1
        brand_prices.setdefault(brand, []).append(float(p.get("current_price") or 0))

        rating = round(float(p.get("rating") or 0))
        if 1 <= rating <= 5:
            rating_counts[rating] += 1

    top_brands = brand_counts.most_common(8)
    avg_price_by_brand = []
    for brand, _ in top_brands[:6]:
        prices = brand_prices.get(brand, [0])
        avg_price_by_brand.append(
            {"brand": brand, "avg_price": round(sum(prices) / len(prices), 0)}
        )

    sentiment_counts = {"Positive": 0, "Negative": 0, "Neutral": 0}
    if reviews:
        for r in reviews:
            label = r.get("sentiment", "Neutral")
            if label in sentiment_counts:
                sentiment_counts[label] += 1
    else:
        for p in products:
            sentiment_counts["Positive"] += int(p.get("positive_reviews") or 0)
            sentiment_counts["Negative"] += int(p.get("negative_reviews") or 0)
            sentiment_counts["Neutral"] += int(p.get("neutral_reviews") or 0)

    return {
        "price_distribution": {
            "labels": price_labels,
            "values": [price_counts[l] for l in price_labels],
        },
        "top_brands": {
            "labels": [b[0] for b in top_brands],
            "values": [b[1] for b in top_brands],
        },
        "avg_price_by_brand": avg_price_by_brand,
        "rating_distribution": {
            "labels": ["1★", "2★", "3★", "4★", "5★"],
            "values": [rating_counts[i] for i in range(1, 6)],
        },
        "sentiment_distribution": {
            "labels": list(sentiment_counts.keys()),
            "values": list(sentiment_counts.values()),
        },
    }


def get_recommendations(products, top_n=10):
    """Return recommended products with scores."""
    engine = RecommendationEngine(min_rating=4.0, min_reviews=5, min_positive_sentiment=50.0)
    payload = []
    for p in products:
        total = int(p.get("total_reviews") or 0)
        pos = int(p.get("positive_reviews") or 0)
        payload.append(
            {
                "product_name": p.get("product_name"),
                "brand_name": p.get("brand_name"),
                "current_price": p.get("current_price"),
                "product_category": p.get("product_category"),
                "product_url": p.get("product_url"),
                "product_image_url": p.get("product_image_url"),
                "avg_rating": float(p.get("rating") or 0),
                "total_reviews": total,
                "sentiment_percentages": {
                    "Positive": round((pos / total) * 100, 1) if total else 0,
                },
            }
        )
    recs = engine.filter_recommendations(payload)
    if not recs:
        recs = sorted(payload, key=lambda x: x.get("avg_rating", 0), reverse=True)
    return recs[:top_n]


def generate_wordcloud_image(reviews):
    """Generate word cloud PNG as base64 string."""
    try:
        from wordcloud import WordCloud
    except ImportError:
        return None

    text = " ".join(r.get("review_text", "") for r in reviews if r.get("review_text"))
    if len(text.strip()) < 10:
        return None

    wc = WordCloud(
        width=800,
        height=400,
        background_color="#0f172a",
        colormap="Oranges",
        max_words=80,
    ).generate(text)

    buffer = io.BytesIO()
    wc.to_image().save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def analyze_review_sentiment(text):
    """Analyze single review text."""
    return SentimentAnalyzer().analyze_sentiment(text)
