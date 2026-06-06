"""
Product Analytics Module - Extracts and analyzes product data
"""
from src.config.logger import logger
import re

class ProductAnalytics:
    """Extracts and calculates product analytics"""
    
    @staticmethod
    def parse_price(price_str):
        """Parse price from string"""
        try:
            # Extract numbers and decimal points
            price = re.findall(r'[\d.]+', price_str.replace(',', ''))
            return float(price[0]) if price else 0.0
        except Exception as e:
            logger.error(f"Error parsing price: {str(e)}")
            return 0.0
    
    @staticmethod
    def calculate_discount(original_price, current_price):
        """Calculate discount percentage"""
        try:
            if original_price == 0:
                return 0.0
            discount = ((original_price - current_price) / original_price) * 100
            return round(max(0, discount), 2)
        except Exception as e:
            logger.error(f"Error calculating discount: {str(e)}")
            return 0.0
    
    @staticmethod
    def extract_brand_from_name(product_name):
        """Extract brand from product name"""
        try:
            brands = [
                "Nike", "Puma", "Adidas", "Reebok", "HRX", "UCB", 
                "Roadster", "HUUB", "Lee", "Wrangler", "Levis", "Biba",
                "Mango", "Forever New", "AND", "Oxolloxo"
            ]
            
            for brand in brands:
                if brand.lower() in product_name.lower():
                    return brand
            
            # Fallback: get first word
            return product_name.split()[0] if product_name else "Unknown"
        except Exception as e:
            logger.error(f"Error extracting brand: {str(e)}")
            return "Unknown"
    
    @staticmethod
    def calculate_rating_from_reviews(reviews_list):
        """Calculate average rating from reviews"""
        try:
            if not reviews_list:
                return 0.0
            
            ratings = []
            for review in reviews_list:
                try:
                    rating = float(review.get("user_rating", 0))
                    ratings.append(rating)
                except (ValueError, TypeError):
                    continue
            
            if ratings:
                return round(sum(ratings) / len(ratings), 2)
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating rating: {str(e)}")
            return 0.0
    
    @staticmethod
    def analyze_review_length(reviews_list):
        """Analyze review lengths"""
        try:
            if not reviews_list:
                return {"avg_length": 0, "max_length": 0, "min_length": 0}
            
            lengths = [len(str(review.get("review_text", ""))) for review in reviews_list]
            
            return {
                "avg_length": round(sum(lengths) / len(lengths), 2) if lengths else 0,
                "max_length": max(lengths) if lengths else 0,
                "min_length": min(lengths) if lengths else 0,
                "total_chars": sum(lengths)
            }
        except Exception as e:
            logger.error(f"Error analyzing review length: {str(e)}")
            return {"avg_length": 0, "max_length": 0, "min_length": 0}
    
    @staticmethod
    def generate_product_summary(product_data, reviews_data, sentiment_dist):
        """Generate comprehensive product summary"""
        try:
            summary = {
                "product_name": product_data.get("product_name", "N/A"),
                "brand_name": product_data.get("brand_name", "N/A"),
                "current_price": product_data.get("current_price", 0),
                "original_price": product_data.get("original_price", 0),
                "discount_percentage": product_data.get("discount_percentage", 0),
                "product_image_url": product_data.get("product_image_url", ""),
                "product_category": product_data.get("product_category", "N/A"),
                "total_reviews": len(reviews_data),
                "avg_rating": ProductAnalytics.calculate_rating_from_reviews(reviews_data),
                "sentiment_distribution": sentiment_dist.get("counts", {}),
                "sentiment_percentages": sentiment_dist.get("percentages", {}),
                "review_length_stats": ProductAnalytics.analyze_review_length(reviews_data)
            }
            return summary
        except Exception as e:
            logger.error(f"Error generating product summary: {str(e)}")
            return {}
