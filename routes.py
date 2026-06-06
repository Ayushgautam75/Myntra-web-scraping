"""Flask API routes for Myntra Analytics Dashboard."""
import csv
import io
import json
import os
import traceback
from datetime import datetime

import pandas as pd
from bson.objectid import ObjectId
from flask import Blueprint, jsonify, request, send_file

import analytics as analytics_engine
import mongodb as mongo
from src.analytics.product_analytics import ProductAnalytics
from src.config.config import Config
from src.config.logger import logger
from src.models.schemas import AnalyticsSchema, ProductSchema, ReviewSchema

api_bp = Blueprint("api", __name__, url_prefix="/api")


def get_db():
    return mongo.get_db()


def friendly_error(exc):
    message = str(exc).lower()
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, ConnectionError) or "mongodb" in message:
        return "Database connection failed. Please verify MongoDB settings."
    if "webdriver" in message or "chrome" in message:
        return "Browser automation failed. Ensure Google Chrome is installed."
    if "timeout" in message:
        return "Request timed out. Please try again."
    return "Something went wrong. Please try again."


def serialize_doc(doc):
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "product_id" in doc and isinstance(doc["product_id"], ObjectId):
        doc["product_id"] = str(doc["product_id"])
    for key in ("created_at", "updated_at", "scrape_timestamp", "timestamp"):
        if key in doc and hasattr(doc[key], "isoformat"):
            doc[key] = doc[key].isoformat()
    return doc


def persist_product(db, product_details, reviews):
    positive = sum(1 for r in reviews if r.get("sentiment") == "Positive")
    negative = sum(1 for r in reviews if r.get("sentiment") == "Negative")
    neutral = sum(1 for r in reviews if r.get("sentiment") == "Neutral")

    if reviews and not product_details.get("rating"):
        product_details["rating"] = ProductAnalytics.calculate_rating_from_reviews(reviews)

    product_details.pop("product_id", None)
    product_details["total_reviews"] = max(len(reviews), int(product_details.get("total_reviews") or 0))
    product_details["positive_reviews"] = positive
    product_details["negative_reviews"] = negative
    product_details["neutral_reviews"] = neutral

    product_doc = ProductSchema.create(**product_details)
    product_id = db.insert_product(product_doc)

    for review in reviews:
        db.insert_review(
            ReviewSchema.create(
                product_id=product_id,
                product_name=product_details.get("product_name"),
                user_name=review.get("user_name", "Anonymous"),
                user_rating=review.get("user_rating", 3),
                review_text=review.get("review_text", "")[:500],
                review_date=review.get("review_date", "N/A"),
                sentiment=review.get("sentiment", "Neutral"),
                sentiment_score=float(review.get("sentiment_score", 0.0)),
            )
        )

    db.store_analytics(
        AnalyticsSchema.create(
            product_id=product_id,
            product_name=product_details.get("product_name", "Unknown"),
            brand_name=product_details.get("brand_name", "Unknown"),
            total_reviews=len(reviews),
            avg_rating=float(product_details.get("rating", 0)),
            sentiment_distribution={"Positive": positive, "Negative": negative, "Neutral": neutral},
            price_data={
                "current": float(product_details.get("current_price", 0)),
                "original": float(product_details.get("original_price", 0)),
                "discount": float(product_details.get("discount_percentage", 0)),
            },
            scrape_timestamp=datetime.now(),
        )
    )
    return serialize_doc({**product_doc, "_id": product_id})


@api_bp.route("/health", methods=["GET"])
def health_check():
    try:
        get_db().get_product_count()
        return jsonify({"status": "healthy", "message": "API is running"})
    except Exception as exc:
        return jsonify({"status": "unhealthy", "message": friendly_error(exc)}), 503


@api_bp.route("/dashboard-stats", methods=["GET"])
def dashboard_stats():
    try:
        return jsonify({"status": "success", "data": get_db().get_dashboard_stats()})
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


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
            "popularity": "total_reviews",
            "created_at": "created_at",
        }
        mongo_sort = [(sort_map.get(sort_field, "created_at"), -1 if sort_order == "desc" else 1)]

        total = db.get_product_count(query)
        products = [serialize_doc(p) for p in db.find_products(query, limit=limit, skip=skip, sort=mongo_sort)]
        return jsonify(
            {
                "status": "success",
                "data": products,
                "total": total,
                "page": page,
                "pages": max((total + limit - 1) // limit, 1),
            }
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/products/filters", methods=["GET"])
def product_filters():
    try:
        db = get_db()
        return jsonify(
            {
                "status": "success",
                "data": {
                    "brands": sorted(filter(None, db.get_distinct_values("brand_name"))),
                    "categories": sorted(filter(None, db.get_distinct_values("product_category"))),
                },
            }
        )
    except Exception as exc:
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
        if sentiment:
            query["sentiment"] = sentiment.capitalize()
        total = db.get_review_count(query)
        reviews = [serialize_doc(r) for r in db.find_reviews(query, limit=limit, skip=skip)]
        return jsonify(
            {
                "status": "success",
                "data": reviews,
                "total": total,
                "page": page,
                "pages": max((total + limit - 1) // limit, 1),
            }
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/charts", methods=["GET"])
def chart_data():
    try:
        db = get_db()
        products = [serialize_doc(p) for p in db.find_products({}, limit=200)]
        reviews = [serialize_doc(r) for r in db.find_reviews({}, limit=500)]
        return jsonify(
            {
                "status": "success",
                "data": analytics_engine.build_chart_data(products, reviews),
            }
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/recommendations", methods=["GET"])
def recommendations():
    try:
        db = get_db()
        products = [serialize_doc(p) for p in db.find_products({}, limit=100, sort=[("rating", -1)])]
        recs = analytics_engine.get_recommendations(products)
        return jsonify({"status": "success", "data": recs})
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/wordcloud", methods=["GET"])
def wordcloud():
    try:
        reviews = [serialize_doc(r) for r in get_db().find_reviews({}, limit=200)]
        image_b64 = analytics_engine.generate_wordcloud_image(reviews)
        if not image_b64:
            return jsonify({"status": "success", "data": None, "message": "Not enough review text."})
        return jsonify({"status": "success", "data": f"data:image/png;base64,{image_b64}"})
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/mongodb/stats", methods=["GET"])
def mongodb_stats():
    try:
        return jsonify({"status": "success", "data": mongo.get_mongo_stats()})
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/logs", methods=["GET"])
def get_logs():
    try:
        log_dir = Config.LOG_DIR
        lines = []
        if os.path.isdir(log_dir):
            files = sorted(
                [f for f in os.listdir(log_dir) if f.endswith(".log")],
                reverse=True,
            )
            if files:
                with open(os.path.join(log_dir, files[0]), encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()[-50:]
        return jsonify({"status": "success", "data": [line.strip() for line in lines]})
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/export/csv", methods=["GET"])
def export_csv():
    try:
        products = list(get_db().products_collection.find())
        if not products:
            return jsonify({"status": "error", "message": "No products to export."}), 400
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "product_name", "brand_name", "current_price", "original_price",
                "discount_percentage", "rating", "total_reviews", "product_url",
            ],
        )
        writer.writeheader()
        for p in products:
            writer.writerow({k: p.get(k, "") for k in writer.fieldnames})
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="myntra_products.csv",
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/export/excel", methods=["GET"])
def export_excel():
    try:
        products = list(get_db().products_collection.find())
        if not products:
            return jsonify({"status": "error", "message": "No products to export."}), 400
        df = pd.DataFrame(
            [
                {
                    "Product Name": p.get("product_name"),
                    "Brand": p.get("brand_name"),
                    "Price": p.get("current_price"),
                    "Original Price": p.get("original_price"),
                    "Discount %": p.get("discount_percentage"),
                    "Rating": p.get("rating"),
                    "Reviews": p.get("total_reviews"),
                    "URL": p.get("product_url"),
                }
                for p in products
            ]
        )
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="myntra_products.xlsx",
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/export/json", methods=["GET"])
def export_json():
    try:
        products = [serialize_doc(p) for p in get_db().find_products({}, limit=1000)]
        if not products:
            return jsonify({"status": "error", "message": "No products to export."}), 400
        payload = json.dumps(products, indent=2, default=str)
        return send_file(
            io.BytesIO(payload.encode("utf-8")),
            mimetype="application/json",
            as_attachment=True,
            download_name="myntra_products.json",
        )
    except Exception as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500


@api_bp.route("/scrape", methods=["POST"])
def scrape_products():
    import scraper as scraper_module

    driver = None
    try:
        data = request.get_json(silent=True) or {}
        search_query = str(data.get("query", "")).strip()
        product_url_input = str(data.get("product_url", "")).strip()
        category = str(data.get("category", "")).strip()

        if not product_url_input and search_query and scraper_module.detect_search_mode(search_query) == "url":
            product_url_input = search_query
            search_query = ""

        try:
            product_count = int(data.get("product_count", 3))
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Products to scrape must be a number."}), 400
        product_count = min(max(product_count, 1), 50)

        if not search_query and not product_url_input:
            return jsonify({"status": "error", "message": "Enter a product name or Myntra URL."}), 400

        db = get_db()
        scraper = scraper_module.get_scraper_class()()
        scraper.initialize_driver()
        driver = scraper

        scraped = []
        errors = 0

        if product_url_input:
            try:
                details, reviews = scraper_module.run_url_scrape(scraper, product_url_input)
                if category:
                    details["product_category"] = category
                scraped.append(persist_product(db, details, reviews))
            except ValueError as exc:
                return jsonify({"status": "error", "message": str(exc)}), 404
            return jsonify(
                {
                    "status": "success",
                    "search_mode": "url",
                    "scraped_count": 1,
                    "requested_count": 1,
                    "data": scraped,
                    "message": "Product scraped from URL.",
                }
            )

        summaries = scraper_module.run_name_search_scrape(scraper, search_query, product_count)
        for idx, cached in enumerate(summaries[:product_count], 1):
            url = cached.get("product_url")
            if not url:
                errors += 1
                continue
            try:
                details = scraper.scrape_product_details(url, cached)
                if category:
                    details["product_category"] = category
                reviews = scraper.scrape_reviews(url, max_reviews=30) or []
                scraped.append(persist_product(db, details, reviews))
            except Exception as exc:
                logger.error(f"Product {idx} failed: {exc}")
                errors += 1

        if not scraped:
            return jsonify({"status": "error", "message": "Could not scrape any products."}), 502

        return jsonify(
            {
                "status": "success",
                "search_mode": "name",
                "scraped_count": len(scraped),
                "requested_count": product_count,
                "error_count": errors,
                "data": scraped,
                "message": f"Scraped {len(scraped)} of {product_count} products.",
            }
        )
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except ConnectionError as exc:
        return jsonify({"status": "error", "message": friendly_error(exc)}), 502
    except Exception as exc:
        logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": friendly_error(exc)}), 500
    finally:
        if driver:
            driver.close()
