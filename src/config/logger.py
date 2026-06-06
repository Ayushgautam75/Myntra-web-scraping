"""
Logging Configuration - Sets up structured logging for the application
"""
import logging
import os
from datetime import datetime
from src.config.config import Config

def setup_logger(name, log_file=None):
    """
    Set up logger with file and console handlers
    
    Args:
        name: Logger name
        log_file: Optional log file path
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file is None:
        log_file = os.path.join(
            Config.LOG_DIR,
            f"{datetime.now().strftime('%Y%m%d')}_{name}.log"
        )
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# Create application logger
logger = setup_logger('myntra_scraper')
