"""
Flask Application Factory - Creates and configures Flask app
"""
from flask import Flask
from flask_cors import CORS
from src.config.config import config
from src.config.logger import logger
from app.backend.routes import api_bp

def create_app(config_obj=None):
    """Create and configure Flask application"""
    
    app = Flask(__name__, 
                template_folder='../frontend/templates',
                static_folder='../frontend/static')
    
    if config_obj is None:
        config_obj = config
    
    # Configure app
    app.config.from_object(config_obj)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Register blueprints
    app.register_blueprint(api_bp)
    
    logger.info("[OK] Flask application created and configured")
    
    return app
