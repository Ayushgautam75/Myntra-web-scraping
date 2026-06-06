"""
Data Schemas - Define the structure for MongoDB documents
"""
from datetime import datetime


def _normalize_sentiment_distribution(sentiment_distribution):
    """Accept Positive/Negative/Neutral or lowercase keys."""
    if not sentiment_distribution:
        return {"Positive": 0, "Negative": 0, "Neutral": 0}

    mapping = {
        "positive": "Positive",
        "negative": "Negative",
        "neutral": "Neutral",
        "Positive": "Positive",
        "Negative": "Negative",
        "Neutral": "Neutral",
    }
    normalized = {"Positive": 0, "Negative": 0, "Neutral": 0}
    for key, value in sentiment_distribution.items():
        label = mapping.get(key, key)
        if label in normalized:
            normalized[label] += int(value or 0)
    return normalized


class ProductSchema:
    """Schema for product documents."""

    @staticmethod
    def create(
        product_name,
        brand_name,
        current_price,
        original_price,
        discount_percentage,
        product_image_url,
        product_category,
        product_url,
        rating=0,
        total_reviews=0,
        positive_reviews=0,
        negative_reviews=0,
        neutral_reviews=0,
    ):
        return {
            "product_name": product_name,
            "brand_name": brand_name,
            "current_price": float(current_price or 0),
            "original_price": float(original_price or 0),
            "discount_percentage": float(discount_percentage or 0),
            "product_image_url": product_image_url or "",
            "product_category": product_category or "N/A",
            "product_url": product_url,
            "rating": float(rating or 0),
            "total_reviews": int(total_reviews or 0),
            "positive_reviews": int(positive_reviews or 0),
            "negative_reviews": int(negative_reviews or 0),
            "neutral_reviews": int(neutral_reviews or 0),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }


class ReviewSchema:
    """Schema for review documents."""

    @staticmethod
    def create(
        product_id,
        user_name,
        user_rating,
        review_text,
        review_date,
        sentiment,
        sentiment_score,
        review_length=None,
        product_name=None,
    ):
        text = review_text or ""
        return {
            "product_id": product_id,
            "product_name": product_name or "",
            "user_name": user_name or "Anonymous",
            "user_rating": int(user_rating or 0),
            "review_text": text,
            "review_date": review_date or "N/A",
            "sentiment": sentiment or "Neutral",
            "sentiment_score": float(sentiment_score or 0.0),
            "review_length": review_length if review_length is not None else len(text),
            "created_at": datetime.now(),
        }


class AnalyticsSchema:
    """Schema for analytics documents."""

    @staticmethod
    def create(
        product_id,
        product_name,
        brand_name,
        total_reviews,
        avg_rating,
        sentiment_distribution,
        price_data,
        scrape_timestamp,
    ):
        normalized = _normalize_sentiment_distribution(sentiment_distribution)
        return {
            "product_id": product_id,
            "product_name": product_name,
            "brand_name": brand_name,
            "total_reviews": int(total_reviews or 0),
            "avg_rating": float(avg_rating or 0),
            "sentiment_distribution": normalized,
            "price_data": {
                "current": float(price_data.get("current", 0)),
                "original": float(price_data.get("original", 0)),
                "discount": float(price_data.get("discount", 0)),
            },
            "scrape_timestamp": scrape_timestamp,
            "timestamp": scrape_timestamp,
            "created_at": datetime.now(),
        }
