"""
Flask application factory for CAN Capture Service

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
from flask import Flask
import os
from app.config import Config


def create_app(config_class=Config):
    """
    Create and configure Flask application
    
    Args:
        config_class: Configuration class to use
        
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    
    # Initialize configuration
    config_class.init_app(app)
    
    # Register blueprints
    from app.routes.web import bp as web_bp
    app.register_blueprint(web_bp)
    
    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Create necessary directories
    os.makedirs(app.config['CAPTURE_DIR'], exist_ok=True)
    os.makedirs(app.config['METADATA_DIR'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['LOG_FILE']), exist_ok=True)
    
    return app

