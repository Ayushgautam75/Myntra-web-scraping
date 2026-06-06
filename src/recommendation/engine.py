"""
Recommendation Engine - Recommends products based on analytics
"""
from src.config.logger import logger

class RecommendationEngine:
    """Recommends products based on defined criteria"""
    
    def __init__(
        self,
        min_rating=4.2,
        min_reviews=100,
        min_positive_sentiment=60.0
    ):
        """
        Initialize recommendation engine with criteria
        
        Args:
            min_rating: Minimum average rating
            min_reviews: Minimum number of reviews
            min_positive_sentiment: Minimum positive sentiment percentage
        """
        self.min_rating = min_rating
        self.min_reviews = min_reviews
        self.min_positive_sentiment = min_positive_sentiment
    
    def is_recommended(self, product_analytics):
        """
        Check if product meets recommendation criteria
        
        Args:
            product_analytics: Product analytics dictionary
        
        Returns:
            bool: True if recommended, False otherwise
        """
        try:
            # Check rating
            rating = product_analytics.get("avg_rating", 0)
            if rating < self.min_rating:
                return False
            
            # Check review count
            total_reviews = product_analytics.get("total_reviews", 0)
            if total_reviews < self.min_reviews:
                return False
            
            # Check positive sentiment percentage
            sentiment_dist = product_analytics.get("sentiment_percentages", {})
            positive_percentage = sentiment_dist.get("Positive", 0)
            if positive_percentage < self.min_positive_sentiment:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking recommendation: {str(e)}")
            return False
    
    def get_recommendation_score(self, product_analytics):
        """
        Calculate recommendation score for product
        
        Returns:
            float: Score between 0 and 100
        """
        try:
            score = 0.0
            
            # Rating score (40%)
            rating = product_analytics.get("avg_rating", 0)
            rating_score = min((rating / 5.0) * 40, 40)
            score += rating_score
            
            # Review count score (30%)
            total_reviews = product_analytics.get("total_reviews", 0)
            review_score = min((total_reviews / 500) * 30, 30)
            score += review_score
            
            # Sentiment score (30%)
            sentiment_dist = product_analytics.get("sentiment_percentages", {})
            positive = sentiment_dist.get("Positive", 0)
            sentiment_score = (positive / 100) * 30
            score += sentiment_score
            
            return round(score, 2)
        except Exception as e:
            logger.error(f"Error calculating recommendation score: {str(e)}")
            return 0.0
    
    def filter_recommendations(self, products_list):
        """
        Filter recommended products from list
        
        Args:
            products_list: List of product analytics dictionaries
        
        Returns:
            list: Recommended products sorted by score
        """
        try:
            recommended = []
            
            for product in products_list:
                if self.is_recommended(product):
                    score = self.get_recommendation_score(product)
                    product["recommendation_score"] = score
                    recommended.append(product)
            
            # Sort by score descending
            recommended.sort(key=lambda x: x.get("recommendation_score", 0), reverse=True)
            
            return recommended
        except Exception as e:
            logger.error(f"Error filtering recommendations: {str(e)}")
            return []
    
    def get_top_recommendations(self, products_list, top_n=10):
        """
        Get top N recommended products
        
        Args:
            products_list: List of product analytics dictionaries
            top_n: Number of top products to return
        
        Returns:
            list: Top N recommended products
        """
        recommended = self.filter_recommendations(products_list)
        return recommended[:top_n]
