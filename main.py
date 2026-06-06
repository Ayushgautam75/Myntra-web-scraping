"""
Main Scraping Orchestrator - Coordinates all scraping operations
"""
import sys
import time
from src.config.logger import logger
from src.config.config import config
from src.scrapper.enhanced_scraper import MyntraEnhancedScraper
from src.analytics.sentiment_analysis import SentimentAnalyzer
from src.analytics.product_analytics import ProductAnalytics
from src.models.database import DatabaseManager
from src.models.schemas import ProductSchema, ReviewSchema, AnalyticsSchema
from src.visualization.visualizer import DataVisualizer
from src.recommendation.engine import RecommendationEngine
from datetime import datetime

class MyntraScrapingOrchestrator:
    """Orchestrates the complete scraping workflow"""
    
    def __init__(self):
        self.scraper = MyntraEnhancedScraper()
        self.db_manager = DatabaseManager()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.visualizer = DataVisualizer()
        self.recommendation_engine = RecommendationEngine()
        self.scraped_count = 0
        self.error_count = 0
    
    def start_scraping(self, search_query, max_products=50):
        """
        Start the complete scraping workflow
        
        Args:
            search_query: Search term (e.g., "white shoes")
            max_products: Maximum products to scrape
        """
        try:
            logger.info("=" * 80)
            logger.info(f"🚀 STARTING SCRAPING WORKFLOW FOR: {search_query}")
            logger.info("=" * 80)
            
            # Initialize browser
            self.scraper.initialize_driver()
            
            # Search for products
            self.scraper.search_products(search_query)
            time.sleep(3)
            
            # Extract product list
            product_urls = self.scraper.extract_product_list()
            
            if not product_urls:
                logger.warning("⚠️ No products found")
                return
            
            # Process each product
            all_products_data = []
            all_reviews_data = []
            analytics_data = []
            
            for idx, product_url in enumerate(product_urls[:max_products], 1):
                logger.info(f"\n📍 Processing Product {idx}/{len(product_urls[:max_products])}")
                
                try:
                    # Scrape product details
                    product_details = self.scraper.scrape_product_details(product_url)
                    if not product_details:
                        self.error_count += 1
                        continue
                    
                    # Scrape reviews
                    reviews = self.scraper.scrape_reviews(product_url, max_reviews=50)
                    
                    if not reviews:
                        logger.warning(f"⚠️ No reviews found for {product_details.get('product_name')}")
                        reviews = []
                    
                    # Analyze reviews and sentiments
                    sentiment_distribution = self.sentiment_analyzer.get_sentiment_distribution(
                        [r.get('review_text', '') for r in reviews]
                    )
                    
                    # Calculate product analytics
                    product_details['rating'] = ProductAnalytics.calculate_rating_from_reviews(reviews)
                    product_details['total_reviews'] = len(reviews)
                    product_details['positive_reviews'] = sentiment_distribution['counts'].get('Positive', 0)
                    product_details['negative_reviews'] = sentiment_distribution['counts'].get('Negative', 0)
                    product_details['neutral_reviews'] = sentiment_distribution['counts'].get('Neutral', 0)
                    
                    # Create product schema
                    product_doc = ProductSchema.create(**product_details)
                    
                    # Store product
                    product_id = self.db_manager.insert_product(product_doc)
                    all_products_data.append(product_doc)
                    
                    # Process and store reviews
                    for review in reviews:
                        review_doc = ReviewSchema.create(
                            product_id=product_id,
                            user_name=review.get('user_name', 'Anonymous'),
                            user_rating=review.get('user_rating', 0),
                            review_text=review.get('review_text', ''),
                            review_date=review.get('review_date', 'N/A'),
                            sentiment=review.get('sentiment', 'Neutral'),
                            sentiment_score=review.get('sentiment_score', 0.0),
                            review_length=len(review.get('review_text', ''))
                        )
                        self.db_manager.insert_review(review_doc)
                        all_reviews_data.append(review_doc)
                    
                    # Create analytics document
                    analytics_doc = AnalyticsSchema.create(
                        product_id=product_id,
                        product_name=product_details.get('product_name'),
                        brand_name=product_details.get('brand_name'),
                        total_reviews=len(reviews),
                        avg_rating=product_details.get('rating', 0),
                        sentiment_distribution=sentiment_distribution['counts'],
                        price_data={
                            'current': product_details.get('current_price', 0),
                            'original': product_details.get('original_price', 0),
                            'discount': product_details.get('discount_percentage', 0)
                        },
                        scrape_timestamp=datetime.now()
                    )
                    self.db_manager.store_analytics(analytics_doc)
                    analytics_data.append(analytics_doc)
                    
                    logger.info(f"[OK] Product stored: {product_details.get('product_name')}")
                    logger.info(f"  - Reviews: {len(reviews)} | Rating: {product_details.get('rating', 0)}")
                    logger.info(f"  - Sentiment: {sentiment_distribution['percentages']}")
                    
                    self.scraped_count += 1
                    
                except Exception as e:
                    logger.error(f"[ERROR] Error processing product: {str(e)}")
                    self.error_count += 1
                    continue
            
            # Generate visualizations
            logger.info("\n📊 Generating visualizations...")
            self.generate_visualizations(all_products_data, all_reviews_data)
            
            # Generate recommendations
            logger.info("\n💎 Generating recommendations...")
            recommendations = self.recommendation_engine.filter_recommendations(
                [{'product_name': p.get('product_name'), 
                   'avg_rating': p.get('rating', 0),
                   'total_reviews': p.get('total_reviews', 0),
                   'sentiment_percentages': {}}
                 for p in all_products_data]
            )
            
            # Print summary
            self.print_summary()
            
            logger.info("=" * 80)
            logger.info("✅ SCRAPING WORKFLOW COMPLETED SUCCESSFULLY!")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"[ERROR] Fatal error in scraping workflow: {str(e)}")
            raise
        
        finally:
            self.scraper.close()
    
    def generate_visualizations(self, products, reviews):
        """Generate all visualizations"""
        try:
            if products:
                logger.info("📈 Generating rating distribution chart...")
                self.visualizer.plot_rating_distribution(reviews)
                
                logger.info("📊 Generating sentiment distribution chart...")
                sentiment_dist = self.sentiment_analyzer.get_sentiment_distribution(
                    [r.get('review_text', '') for r in reviews]
                )
                self.visualizer.plot_sentiment_distribution(sentiment_dist)
                
                logger.info("💰 Generating price distribution chart...")
                self.visualizer.plot_price_distribution(products)
                
                logger.info("🏆 Generating brand comparison chart...")
                self.visualizer.plot_brand_comparison(products)
                
                logger.info("⭐ Generating top products chart...")
                self.visualizer.plot_top_products(products, metric='rating')
                
                logger.info("[OK] All visualizations generated successfully")
        except Exception as e:
            logger.error(f"[ERROR] Error generating visualizations: {str(e)}")
    
    def print_summary(self):
        """Print scraping summary"""
        logger.info("\n" + "=" * 80)
        logger.info("📋 SCRAPING SUMMARY")
        logger.info("=" * 80)
        logger.info(f"[OK] Successfully scraped: {self.scraped_count} products")
        logger.info(f"[ERROR] Errors encountered: {self.error_count}")
        
        total_products = self.db_manager.get_product_count()
        total_reviews = self.db_manager.get_review_count()
        
        logger.info(f"\n📊 Database Statistics:")
        logger.info(f"   - Total Products: {total_products}")
        logger.info(f"   - Total Reviews: {total_reviews}")
        logger.info(f"   - Avg Reviews per Product: {total_reviews // max(total_products, 1)}")
        
        logger.info(f"\n📁 Output Files:")
        logger.info(f"   - Visualizations: data/visualizations/")
        logger.info(f"   - Logs: logs/")
        logger.info("=" * 80 + "\n")

def main():
    """Main entry point"""
    try:
        # Example usage
        search_query = "white shoes"
        max_products = 3
        
        orchestrator = MyntraScrapingOrchestrator()
        orchestrator.start_scraping(search_query, max_products)
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Scraping interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"[ERROR] Application error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
