#!/usr/bin/env python3
"""
Application entry point for CAN Capture Service

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
from app import create_app
from app.config import Config
from app.utils.logger import setup_logging

# Create Flask application
app = create_app(Config)

# Setup logging
setup_logging(app)

if __name__ == '__main__':
    app.logger.info('Starting CAN Capture Service...')
    app.logger.info(f'Server: {app.config["HOST"]}:{app.config["PORT"]}')
    app.logger.info(f'Debug mode: {app.config["DEBUG"]}')
    
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )

