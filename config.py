"""
PharmaCheck Configuration
Environment-based configuration for the application
"""

import os
from datetime import timedelta

# Try to load from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    """Base configuration class"""
    
    # Database Configuration
    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        'mysql+mysqlconnector://root:password@localhost:3306/pharmacheck'
    )
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'pharmacheck-dev-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600)))
    JWT_ALGORITHM = 'HS256'
    
    # Ollama Configuration
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2:3b')
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'pharmacheck-flask-secret')
    DEBUG = os.getenv('FLASK_DEBUG', '1') == '1'
    
    # Rate limiting
    RATE_LIMIT_AUTH = 5  # requests per minute for auth endpoints
    RATE_LIMIT_API = 60  # requests per minute for API endpoints


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    # Override with production values
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')  # Must be set in production
    

# Get config based on environment
def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        return ProductionConfig()
    return DevelopmentConfig()


config = get_config()

