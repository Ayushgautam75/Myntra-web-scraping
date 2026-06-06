"""
Flask Backend Routes - API endpoints for the dashboard
"""
import csv
import io
import traceback
from datetime import datetime

from bson.objectid import ObjectId
from flask import Blueprint, jsonify, request, send_file

from src.analytics.product_analytics import ProductAnalytics
from src.config.logger import logger

api_bp = Blueprint("api", __name__, url_prefix="/api")

_db_manager = None


def get_db():
    """Lazy database manager initialization."""
    global _db_manager
    if _db_manager is None:
        from src.models.database import DatabaseManager

        _db_manager = DatabaseManager()
    return _db_manager


def friendly_error(exc):
    """Map internal exceptions to user-friendly messages."""
    message = str(exc).lower()
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, ConnectionError) or "mongodb" in message or "connection" in message:
        return "Database connection failed. Please verify MongoDB is running and configured."
    if "webdriver" in message or "chrome" in message or "browser" in message:
        return "Browser automation failed. Please ensure Google Chrome is installed."
    if "timeout" in message:
        return "The request timed out. Myntra may be slow or blocking requests. Please try again."
    return "Something went wrong while processing your request. Please try again."


def _persist_product(db, product_details, reviews):
    """Save product, reviews, and analytics to MongoDB."""
    from src.models.schemas import AnalyticsSchema, ProductSchema, ReviewSchema

    positive_count = sum(1 for r in reviews if r.get("sentiment") == "Positive")
    negative_count = sum(1 for r in reviews if r.get("sentiment") == "Negative")
    neutral_count = sum(1 for r in reviews if r.get("sentiment") == "Neutral")

    if reviews and not product_details.get("rating"):
        product_details["rating"] = ProductAnalytics.calculate_rating_from_reviews(reviews)

    product_details.pop("product_id", None)
    product_details["total_reviews"] = max(
        len(reviews), int(product_details.get("total_reviews") or 0)
    )
    product_details["positive_reviews"] = positive_count
    product_details["negative_reviews"] = negative_count
    product_details["neutral_reviews"] = neutral_count

    product_doc = ProductSchema.create(**product_details)
    product_id = db.insert_product(product_doc)

    for review in reviews:
        review_doc = ReviewSchema.create(
            product_id=product_id,
            product_name=product_details.get("product_name"),
            user_name=review.get("user_name", "Anonymous"),
            user_rating=review.get("user_rating", 3),
            review_text=review.get("review_text", "")[:500],
            review_date=review.get("review_date", "N/A"),
            sentiment=review.get("sentiment", "Neutral"),
            sentiment_score=float(review.get("sentiment_score", 0.0)),
        )
        db.insert_review(review_doc)

    analytics_doc = AnalyticsSchema.create(
        product_id=product_id,
        product_name=product_details.get("product_name", "Unknown"),
        brand_name=product_details.get("brand_name", "Unknown"),
        total_reviews=len(reviews),
        avg_rating=float(product_details.get("rating", 0)),
        sentiment_distribution={
            "Positive": positive_count,
            "Negative": negative_count,
            "Neutral": neutral_count,
        },
        price_data={
            "current": float(product_details.get("current_price", 0)),
            "original": float(product_details.get("original_price", 0)),
            "discount": float(product_details.get("discount_percentage", 0)),
        },
        scrape_timestamp=datetime.now(),
    )
    db.store_analytics(analytics_doc)

    return serialize_doc({**product_doc, "_id": product_id})


def serialize_doc(doc):
    """Convert MongoDB document for JSON response."""
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "product_id" in doc and isinstance(doc["product_id"], ObjectId):
        doc["product_id"] = str(doc["product_id"])
    return doc


@api_bp.route("/health", methods=["GET"])
def health_check():
    try:
        get_db().get_product_count()
        return jsonify({"status": "healthy", "message": "API is running"})
    except Exception as exc:
        logger.error(f"Health check failed: {exc}")
        return jsonify(
            {"status": "unhealthy", "message": friendly_error(exc)}
        ), 503


@api_bp.route("/products", methods=["GET"])
def get_products():
    try:
        db = get_db()
        page = max(request.args.get("page", 1, type=int), 1)
        limit = min(max(request.args.get("limit", 10, type=int), 1), 100)
        skip = (page - 1) * limit

        query = {}
        search = request.args.get("q", "").strip()
        brand = request.args.get("brand", "").strip()
        category = request.args.get("category", "").strip()
        min_price = request.args.get("min_price", type=float)
        max_price = request.args.get("max_price", type=float)
        min_rating = request.args.get("min_rating", type=float)

        if search:
            query["$or"] = [
                {"product_name": {"$regex": search, "$options": "i"}},
                {"brand_name": {"$regex": search, "$options": "i"}},
                {"product_category": {"$regex": search, "$options": "i"}},
            ]
        if brand:
            query["brand_name"] = {"$regex": f"^{brand}$", "$options": "i"}
        if category:
            query["product_category"] = {"$regex": category, "$options": "i"}
        if min_price is not None or max_price is not None:
            query["current_price"] = {}
            if min_price is not None:
                query["current_price"]["$gte"] = min_price
            if max_price is not None:
                query["current_price"]["$lte"] = max_price
        if min_rating is not None:
            query["rating"] = {"$gte": min_rating}

        sort_field = request.args.get("sort", "created_at")
        sort_order = request.args.get("order", "desc")
        sort_map = {
            "price": "current_price",
            "rating": "rating",
            "name": "product_name",
            "brand": "brand_name",
            "reviews": "total_reviews",
            "created_at": "created_at",
        }
        mongo_sort = [(sort_map.get(sort_field, "created_at"), -1 if sort_order == "desc" else 1)]

        total_count = db.get_product_count(query)
        products = db.find_products(query=query, limit=limit, skip=skip, sort=mongo_sort)
        products = [serialize_doc(p) for p in products]

        return jsonify(
            {
                "status": "success",
                "data": products,
                "total": total_count,
                "page": page,
                "pages": max((total_count + limit - 1) // limit, 1),
            }
        )
    except Exception as exc:
        logger.error(f"Error fetching products: {exc}")
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/products/filters", methods=["GET"])
def get_product_filters():
    try:
        db = get_db()
        return jsonify(
            {
                "status": "success",
                "data": {
                    "brands": sorted(filter(None, db.get_distinct_values("brand_name"))),
                    "categories": sorted(
                        filter(None, db.get_distinct_values("product_category"))
                    ),
                },
            }
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/products/<product_id>/reviews", methods=["GET"])
def get_product_reviews(product_id):
    try:
        db = get_db()
        page = max(request.args.get("page", 1, type=int), 1)
        limit = min(max(request.args.get("limit", 10, type=int), 1), 100)
        skip = (page - 1) * limit

        query = {"product_id": ObjectId(product_id)}
        sentiment = request.args.get("sentiment", "").strip()
        min_rating = request.args.get("min_rating", type=int)
        max_rating = request.args.get("max_rating", type=int)

        if sentiment:
            query["sentiment"] = sentiment.capitalize()
        if min_rating is not None:
            query.setdefault("user_rating", {})["$gte"] = min_rating
        if max_rating is not None:
            query.setdefault("user_rating", {})["$lte"] = max_rating

        total_count = db.get_review_count(query)
        reviews = db.find_reviews(query=query, limit=limit, skip=skip, sort=[("created_at", -1)])
        reviews = [serialize_doc(r) for r in reviews]

        return jsonify(
            {
                "status": "success",
                "data": reviews,
                "total": total_count,
                "page": page,
                "pages": max((total_count + limit - 1) // limit, 1),
            }
        )
    except Exception as exc:
        logger.error(f"Error fetching product reviews: {exc}")
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/reviews", methods=["GET"])
def get_reviews():
    try:
        db = get_db()
        page = max(request.args.get("page", 1, type=int), 1)
        limit = min(max(request.args.get("limit", 20, type=int), 1), 100)
        skip = (page - 1) * limit

        query = {}
        sentiment = request.args.get("sentiment", "").strip()
        min_rating = request.args.get("min_rating", type=int)
        max_rating = request.args.get("max_rating", type=int)
        search = request.args.get("q", "").strip()

        if sentiment:
            query["sentiment"] = sentiment.capitalize()
        if min_rating is not None:
            query.setdefault("user_rating", {})["$gte"] = min_rating
        if max_rating is not None:
            query.setdefault("user_rating", {})["$lte"] = max_rating
        if search:
            query["$or"] = [
                {"review_text": {"$regex": search, "$options": "i"}},
                {"user_name": {"$regex": search, "$options": "i"}},
                {"product_name": {"$regex": search, "$options": "i"}},
            ]

        total_count = db.get_review_count(query)
        reviews = db.find_reviews(query=query, limit=limit, skip=skip, sort=[("created_at", -1)])
        reviews = [serialize_doc(r) for r in reviews]

        if not reviews and total_count == 0:
            return jsonify(
                {
                    "status": "success",
                    "data": [],
                    "total": 0,
                    "page": page,
                    "pages": 1,
                    "message": "No reviews found yet. Scrape products to collect reviews.",
                }
            )

        return jsonify(
            {
                "status": "success",
                "data": reviews,
                "total": total_count,
                "page": page,
                "pages": max((total_count + limit - 1) // limit, 1),
            }
        )
    except Exception as exc:
        logger.error(f"Error fetching reviews: {exc}")
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/analytics", methods=["GET"])
def get_analytics():
    try:
        db = get_db()
        analytics = list(
            db.analytics_collection.find().sort("timestamp", -1).limit(100)
        )
        analytics = [serialize_doc(item) for item in analytics]
        return jsonify({"status": "success", "data": analytics})
    except Exception as exc:
        logger.error(f"Error fetching analytics: {exc}")
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/dashboard-stats", methods=["GET"])
def get_dashboard_stats():
    try:
        stats = get_db().get_dashboard_stats()
        return jsonify({"status": "success", "data": stats})
    except Exception as exc:
        logger.error(f"Error fetching dashboard stats: {exc}")
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/search", methods=["GET"])
def search_products():
    try:
        query_str = request.args.get("q", "").strip()
        if not query_str:
            return jsonify({"status": "error", "message": "Search query is required."}), 400

        db = get_db()
        search_query = {
            "$or": [
                {"product_name": {"$regex": query_str, "$options": "i"}},
                {"brand_name": {"$regex": query_str, "$options": "i"}},
                {"product_category": {"$regex": query_str, "$options": "i"}},
            ]
        }
        products = db.find_products(query=search_query, limit=20)
        products = [serialize_doc(p) for p in products]

        if not products:
            return jsonify(
                {
                    "status": "success",
                    "data": [],
                    "message": f"No products found matching '{query_str}'. Try scraping first.",
                }
            )

        return jsonify({"status": "success", "data": products})
    except Exception as exc:
        logger.error(f"Error searching products: {exc}")
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/export/csv", methods=["GET"])
def export_csv():
    try:
        db = get_db()
        products = list(db.products_collection.find())
        if not products:
            return jsonify({"status": "error", "message": "No products to export."}), 400

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "product_name",
                "brand_name",
                "current_price",
                "original_price",
                "discount_percentage",
                "product_category",
                "rating",
                "total_reviews",
                "product_url",
            ],
        )
        writer.writeheader()
        for product in products:
            writer.writerow(
                {
                    "product_name": product.get("product_name", ""),
                    "brand_name": product.get("brand_name", ""),
                    "current_price": product.get("current_price", ""),
                    "original_price": product.get("original_price", ""),
                    "discount_percentage": product.get("discount_percentage", ""),
                    "product_category": product.get("product_category", ""),
                    "rating": product.get("rating", ""),
                    "total_reviews": product.get("total_reviews", ""),
                    "product_url": product.get("product_url", ""),
                }
            )

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="products.csv",
        )
    except Exception as exc:
        logger.error(f"Error exporting CSV: {exc}")
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/scrape", methods=["POST"])
def scrape_products():
    scraper = None
    try:
        from src.scrapper.enhanced_scraper import (
            MyntraEnhancedScraper,
            detect_search_mode,
            normalize_myntra_url,
        )

        data = request.get_json(silent=True) or {}
        search_query = str(data.get("query", "")).strip()
        product_url_input = str(data.get("product_url", "")).strip()

        # Support legacy single-field requests
        if not product_url_input and search_query and detect_search_mode(search_query) == "url":
            product_url_input = search_query
            search_query = ""

        try:
            product_count = int(data.get("product_count", data.get("max_products", 3)))
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Products to scrape must be a number."}), 400

        product_count = min(max(product_count, 1), 50)

        if not search_query and not product_url_input:
            return jsonify(
                {"status": "error", "message": "Enter a product name or a Myntra product URL."}
            ), 400

        search_mode = "url" if product_url_input else "name"
        db = get_db()
        scraper = MyntraEnhancedScraper()
        scraper.initialize_driver()

        scraped_products = []
        scraped_count = 0
        error_count = 0

        if search_mode == "url":
            try:
                product_url = normalize_myntra_url(product_url_input)
            except ValueError as exc:
                return jsonify({"status": "error", "message": str(exc)}), 400

            logger.info(f"[START] Direct URL scrape: {product_url}")
            try:
                product_details, reviews = scraper.scrape_product_by_url(product_url)
                saved = _persist_product(db, product_details, reviews)
                scraped_products.append(saved)
                scraped_count = 1
            except ValueError as exc:
                return jsonify({"status": "error", "message": str(exc)}), 404
            except Exception as exc:
                logger.error(f"[ERROR] URL scrape failed: {exc}")
                return jsonify(
                    {
                        "status": "error",
                        "message": "Could not scrape this product URL. Please verify the link.",
                    }
                ), 502

            return jsonify(
                {
                    "status": "success",
                    "message": "Successfully scraped product from URL.",
                    "search_mode": "url",
                    "product_count": 1,
                    "requested_count": 1,
                    "data": scraped_products,
                    "scraped_count": scraped_count,
                    "error_count": 0,
                }
            )

        logger.info(f"[START] Product name search: {search_query} (count={product_count})")
        if not scraper.search_products(search_query):
            return jsonify(
                {"status": "error", "message": "Could not reach Myntra. Please try again later."}
            ), 502

        search_products_data = scraper.extract_products_from_search(product_count=product_count)
        if not search_products_data:
            return jsonify(
                {
                    "status": "error",
                    "message": f"No products found for '{search_query}'. Try a different search term.",
                }
            ), 404

        for idx, cached_product in enumerate(search_products_data[:product_count], 1):
            product_url = cached_product.get("product_url")
            if not product_url:
                error_count += 1
                continue

            try:
                logger.info(
                    f"[INFO] Processing product {idx}/{min(len(search_products_data), product_count)}"
                )
                product_details = scraper.scrape_product_details(product_url, cached_product)
                if not product_details or not product_details.get("product_name"):
                    error_count += 1
                    continue

                reviews = scraper.scrape_reviews(product_url, max_reviews=30) or []
                saved = _persist_product(db, product_details, reviews)
                scraped_products.append(saved)
                scraped_count += 1
            except Exception as exc:
                logger.error(f"[ERROR] Error processing product: {exc}")
                logger.error(traceback.format_exc())
                error_count += 1

        if scraped_count == 0:
            return jsonify(
                {
                    "status": "error",
                    "message": "Could not scrape any products. Myntra may have changed or blocked the request.",
                    "scraped_count": 0,
                    "error_count": error_count,
                }
            ), 502

        return jsonify(
            {
                "status": "success",
                "message": f"Successfully scraped {scraped_count} of {product_count} requested products.",
                "search_mode": "name",
                "product_count": product_count,
                "requested_count": product_count,
                "data": scraped_products,
                "scraped_count": scraped_count,
                "error_count": error_count,
            }
        )
    except RuntimeError as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 503
    except ConnectionError as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 503
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        logger.error(f"[ERROR] Scrape endpoint failed: {exc}")
        logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500
    finally:
        if scraper:
            scraper.close()


@api_bp.errorhandler(404)
def not_found(_error):
    return jsonify({"status": "error", "message": "Endpoint not found."}), 404


@api_bp.errorhandler(500)
def internal_error(_error):
    return jsonify({"status": "error", "message": "Internal server error."}), 500
