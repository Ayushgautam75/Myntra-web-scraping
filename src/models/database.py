"""
Database Module - Handles all MongoDB operations
"""
from datetime import datetime

from pymongo import ASCENDING, MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError, ServerSelectionTimeoutError

from src.config.config import Config
from src.config.logger import logger


class MongoDBConnection:
    """Singleton class for MongoDB connection."""

    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self):
        """Establish MongoDB connection."""
        if self._client is not None:
            return self._client
        try:
            self._client = MongoClient(
                Config.get_mongodb_connection_string(),
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
            )
            self._client.admin.command("ping")
            logger.info("[OK] MongoDB Connection Successful")
            return self._client
        except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
            logger.error(f"[ERROR] MongoDB Connection Failed: {exc}")
            raise ConnectionError(
                "Unable to connect to MongoDB. Please check your connection settings."
            ) from exc

    def get_database(self, db_name=None):
        if db_name is None:
            db_name = Config.DATABASE_NAME
        if self._client is None:
            self.connect()
        return self._client[db_name]

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("MongoDB Connection Closed")


class DatabaseManager:
    """Manager for database operations."""

    def __init__(self):
        self.connection = MongoDBConnection()
        self.db = self.connection.get_database()
        self.products_collection = self.db[Config.PRODUCTS_COLLECTION]
        self.reviews_collection = self.db[Config.REVIEWS_COLLECTION]
        self.analytics_collection = self.db[Config.ANALYTICS_COLLECTION]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create indexes to prevent duplicate records."""
        try:
            self.products_collection.create_index(
                [("product_url", ASCENDING)], unique=True, sparse=True
            )
            self.reviews_collection.create_index(
                [
                    ("product_id", ASCENDING),
                    ("user_name", ASCENDING),
                    ("review_text", ASCENDING),
                ],
                unique=True,
            )
            self.analytics_collection.create_index([("product_id", ASCENDING)])
        except Exception as exc:
            logger.warning(f"Index creation warning: {exc}")

    def insert_product(self, product_data):
        """Insert or update product by product_url."""
        try:
            product_data = dict(product_data)
            product_data["updated_at"] = datetime.now()
            url = product_data.get("product_url")
            if url:
                existing = self.products_collection.find_one({"product_url": url})
                if existing:
                    self.products_collection.update_one(
                        {"_id": existing["_id"]},
                        {"$set": product_data},
                    )
                    logger.info(f"Product updated: {existing['_id']}")
                    return existing["_id"]

            result = self.products_collection.insert_one(product_data)
            logger.info(f"Product inserted: {result.inserted_id}")
            return result.inserted_id
        except DuplicateKeyError:
            existing = self.products_collection.find_one(
                {"product_url": product_data.get("product_url")}
            )
            if existing:
                return existing["_id"]
            raise
        except Exception as exc:
            logger.error(f"Error inserting product: {exc}")
            raise

    def insert_products_batch(self, products):
        ids = []
        for product in products:
            ids.append(self.insert_product(product))
        return ids

    def find_products(self, query=None, limit=10, skip=0, sort=None):
        query = query or {}
        cursor = self.products_collection.find(query).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        return list(cursor)

    def insert_review(self, review_data):
        """Insert review if not duplicate."""
        try:
            result = self.reviews_collection.insert_one(review_data)
            return result.inserted_id
        except DuplicateKeyError:
            logger.debug("Duplicate review skipped")
            return None
        except Exception as exc:
            logger.error(f"Error inserting review: {exc}")
            raise

    def insert_reviews_batch(self, reviews):
        ids = []
        for review in reviews:
            review_id = self.insert_review(review)
            if review_id:
                ids.append(review_id)
        return ids

    def store_analytics(self, analytics_data):
        try:
            analytics_data = dict(analytics_data)
            analytics_data["timestamp"] = datetime.now()
            product_id = analytics_data.get("product_id")
            if product_id:
                self.analytics_collection.update_one(
                    {"product_id": product_id},
                    {"$set": analytics_data},
                    upsert=True,
                )
                doc = self.analytics_collection.find_one({"product_id": product_id})
                return doc["_id"] if doc else None
            result = self.analytics_collection.insert_one(analytics_data)
            return result.inserted_id
        except Exception as exc:
            logger.error(f"Error storing analytics: {exc}")
            raise

    def get_analytics_trend(self, days=30):
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)
        return list(self.analytics_collection.find({"timestamp": {"$gte": start_date}}))

    def get_product_count(self, query=None):
        return self.products_collection.count_documents(query or {})

    def get_review_count(self, query=None):
        return self.reviews_collection.count_documents(query or {})

    def get_dashboard_stats(self):
        """Aggregate dashboard metrics."""
        product_count = self.get_product_count()
        review_count = self.get_review_count()

        price_pipeline = [
            {"$group": {"_id": None, "avg_price": {"$avg": "$current_price"}}}
        ]
        price_result = list(self.products_collection.aggregate(price_pipeline))
        avg_price = round(price_result[0]["avg_price"], 2) if price_result else 0

        rating_pipeline = [
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}
        ]
        rating_result = list(self.products_collection.aggregate(rating_pipeline))
        avg_rating = round(rating_result[0]["avg_rating"], 2) if rating_result else 0

        brands = self.products_collection.distinct("brand_name")
        brands_found = len([b for b in brands if b])

        sentiment_pipeline = [
            {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}}
        ]
        sentiment_data = list(self.reviews_collection.aggregate(sentiment_pipeline))

        return {
            "total_products": product_count,
            "total_reviews": review_count,
            "avg_price": avg_price,
            "avg_rating": avg_rating,
            "brands_found": brands_found,
            "sentiment_distribution": sentiment_data,
        }

    def get_distinct_values(self, field):
        return self.products_collection.distinct(field)

    def find_reviews(self, query=None, limit=20, skip=0, sort=None):
        query = query or {}
        cursor = self.reviews_collection.find(query).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        return list(cursor)
