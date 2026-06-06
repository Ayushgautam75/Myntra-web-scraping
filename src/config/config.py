"""
Configuration Module - Manages all environment variables and settings
"""
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    
    # MongoDB Configuration
    MONGO_URI = os.getenv("MONGO_DB_URL", "mongodb://localhost:27017/")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "myntra_data")
    
    # Collections
    PRODUCTS_COLLECTION = "products"
    REVIEWS_COLLECTION = "reviews"
    ANALYTICS_COLLECTION = "analytics"
    
    # Flask Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", False)
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = "logs"
    
    # Data Directories
    DATA_DIR = "data"
    EXPORT_DIR = os.path.join(DATA_DIR, "exports")
    
    # Scraping Configuration
    CHROME_DRIVER_PATH = None  # webdriver-manager will handle this
    REQUEST_TIMEOUT = 10
    RETRY_ATTEMPTS = 3
    
    # Pagination
    ITEMS_PER_PAGE = 10
    MAX_PAGES = 10
    
    @classmethod
    def get_mongodb_connection_string(cls):
        """Get MongoDB connection string"""
        return cls.MONGO_URI
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist"""
        for directory in [cls.LOG_DIR, cls.DATA_DIR, cls.EXPORT_DIR]:
            os.makedirs(directory, exist_ok=True)

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    MONGO_URI = "mongodb://localhost:27017/myntra_test"

# Select configuration based on environment
ENV = os.getenv("FLASK_ENV", "development")
if ENV == "production":
    config = ProductionConfig
elif ENV == "testing":
    config = TestingConfig
else:
    config = DevelopmentConfig

# Ensure directories exist
config.ensure_directories()
