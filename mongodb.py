"""MongoDB operations for Myntra Analytics Dashboard."""
from src.models.database import DatabaseManager

_db_instance = None


def get_db():
    """Return singleton DatabaseManager instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance


def get_mongo_stats():
    """Return MongoDB collection statistics."""
    db = get_db()
    return {
        "products": db.get_product_count(),
        "reviews": db.get_review_count(),
        "analytics": db.analytics_collection.count_documents({}),
        "database": db.db.name,
    }
