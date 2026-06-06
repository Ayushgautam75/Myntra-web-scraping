"""
Data Visualization Module - Creates charts and visualizations
"""
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from src.config.logger import logger
import os

class DataVisualizer:
    """Creates data visualizations"""
    
    def __init__(self, style="dark_background"):
        """Initialize visualizer with style"""
        plt.style.use(style)
        sns.set_palette("husl")
        self.output_dir = "data/visualizations"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def plot_rating_distribution(self, reviews_data, save_path=None):
        """Plot rating distribution"""
        try:
            ratings = [r.get("user_rating", 0) for r in reviews_data]
            
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(ratings, bins=5, color='skyblue', edgecolor='black', alpha=0.7)
            ax.set_xlabel('Rating', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            ax.set_title('Rating Distribution', fontsize=14, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            
            if save_path is None:
                save_path = os.path.join(self.output_dir, 'rating_distribution.png')
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Rating distribution chart saved: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"Error plotting rating distribution: {str(e)}")
            return None
    
    def plot_sentiment_distribution(self, sentiment_data, save_path=None):
        """Plot sentiment distribution"""
        try:
            sentiments = sentiment_data.get("counts", {})
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
            
            # Bar chart
            colors = ['green', 'red', 'gray']
            ax1.bar(sentiments.keys(), sentiments.values(), color=colors, alpha=0.7, edgecolor='black')
            ax1.set_ylabel('Count', fontsize=12)
            ax1.set_title('Sentiment Distribution (Count)', fontsize=12, fontweight='bold')
            ax1.grid(axis='y', alpha=0.3)
            
            # Pie chart
            percentages = sentiment_data.get("percentages", {})
            ax2.pie(
                percentages.values(),
                labels=percentages.keys(),
                autopct='%1.1f%%',
                colors=colors,
                startangle=90
            )
            ax2.set_title('Sentiment Distribution (Percentage)', fontsize=12, fontweight='bold')
            
            if save_path is None:
                save_path = os.path.join(self.output_dir, 'sentiment_distribution.png')
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Sentiment distribution chart saved: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"Error plotting sentiment distribution: {str(e)}")
            return None
    
    def plot_price_distribution(self, products_data, save_path=None):
        """Plot price distribution"""
        try:
            prices = [p.get("current_price", 0) for p in products_data]
            
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(prices, bins=20, color='lightcoral', edgecolor='black', alpha=0.7)
            ax.set_xlabel('Price (₹)', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            ax.set_title('Price Distribution', fontsize=14, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            
            if save_path is None:
                save_path = os.path.join(self.output_dir, 'price_distribution.png')
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Price distribution chart saved: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"Error plotting price distribution: {str(e)}")
            return None
    
    def plot_brand_comparison(self, products_data, save_path=None):
        """Plot brand comparison"""
        try:
            df = pd.DataFrame(products_data)
            brand_data = df.groupby('brand_name').agg({
                'current_price': 'mean',
                'product_name': 'count'
            }).rename(columns={'product_name': 'count'}).sort_values('current_price', ascending=False).head(10)
            
            fig, ax = plt.subplots(figsize=(12, 6))
            brand_data['current_price'].plot(kind='barh', ax=ax, color='steelblue', edgecolor='black')
            ax.set_xlabel('Average Price (₹)', fontsize=12)
            ax.set_title('Top 10 Brands by Average Price', fontsize=14, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)
            
            if save_path is None:
                save_path = os.path.join(self.output_dir, 'brand_comparison.png')
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Brand comparison chart saved: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"Error plotting brand comparison: {str(e)}")
            return None
    
    def plot_top_products(self, products_data, metric='rating', save_path=None):
        """Plot top products by metric"""
        try:
            df = pd.DataFrame(products_data)
            top_products = df.nlargest(10, metric if metric in df.columns else 'rating')
            
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.barh(top_products['product_name'][::-1], top_products[metric][::-1], 
                   color='mediumpurple', edgecolor='black', alpha=0.7)
            ax.set_xlabel(metric.capitalize(), fontsize=12)
            ax.set_title(f'Top 10 Products by {metric.capitalize()}', fontsize=14, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)
            
            if save_path is None:
                save_path = os.path.join(self.output_dir, f'top_products_{metric}.png')
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Top products chart saved: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"Error plotting top products: {str(e)}")
            return None
