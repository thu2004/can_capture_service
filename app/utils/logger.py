"""
Logging configuration and setup
"""
import logging
import logging.handlers
import yaml
from pathlib import Path


# Global flags to track if logging has been initialized
_frontend_logging_initialized = False
_backend_logging_initialized = False


def _setup_logging_from_config(log_level_str='INFO', log_file_path='./logs/app.log', 
                                max_size_mb=100, backup_count=5, log_type='frontend'):
    """
    Internal function to setup logging with given parameters
    
    Args:
        log_level_str: Log level as string (e.g., 'INFO', 'DEBUG')
        log_file_path: Path to log file
        max_size_mb: Maximum log file size in MB
        backup_count: Number of backup files to keep
        log_type: Type of logger ('frontend' or 'backend')
    """
    global _frontend_logging_initialized, _backend_logging_initialized
    
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    log_file = Path(log_file_path)
    
    # Create log directory if it doesn't exist
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Get or create a logger for this type
    if log_type == 'frontend':
        logger_name = 'frontend'
    else:
        logger_name = 'backend'
    
    app_logger = logging.getLogger(logger_name)
    app_logger.setLevel(log_level)
    app_logger.propagate = False  # Don't propagate to root logger
    
    # Check if already initialized for this type
    if log_type == 'frontend' and _frontend_logging_initialized:
        return app_logger
    if log_type == 'backend' and _backend_logging_initialized:
        return app_logger
    
    # Clear existing handlers for this logger
    app_logger.handlers.clear()
    
    # File handler with rotation
    max_bytes = max_size_mb * 1024 * 1024  # Convert MB to bytes
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    app_logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    app_logger.addHandler(console_handler)
    
    # Mark as initialized
    if log_type == 'frontend':
        _frontend_logging_initialized = True
    else:
        _backend_logging_initialized = True
    
    app_logger.info(f'{log_type.capitalize()} logging configured: level={logging.getLevelName(log_level)}, file={log_file}, max_size={max_size_mb}MB')
    return app_logger


def setup_logging(app):
    """
    Configure logging for the frontend application
    
    Args:
        app: Flask application instance
    """
    # Get logging configuration from app config
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    log_file = app.config.get('LOG_FILE', './logs/frontend.log')
    max_size_mb = app.config.get('LOG_MAX_SIZE_MB', 100)
    backup_count = app.config.get('LOG_BACKUP_COUNT', 5)
    
    _setup_logging_from_config(log_level, str(log_file), max_size_mb, backup_count, log_type='frontend')
    
    # Set Flask logger to use frontend logger
    frontend_logger = logging.getLogger('frontend')
    app.logger.handlers = frontend_logger.handlers[:]
    app.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def setup_logging_standalone(log_type='backend'):
    """
    Setup logging for standalone processes (like workers) that don't have Flask app context.
    Reads configuration from config.yaml file.
    
    Args:
        log_type: Type of logger ('frontend' or 'backend'), defaults to 'backend'
    """
    try:
        # Try to load config from config.yaml
        config_file = Path(__file__).parent.parent.parent / 'config.yaml'
        if config_file.exists():
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            logging_config = config_data.get('logging', {})
            log_level = logging_config.get('level', 'INFO')
            
            # Get log type specific config
            if log_type == 'frontend':
                type_config = logging_config.get('frontend', {})
                log_file = type_config.get('file', './logs/frontend.log')
                max_size_mb = type_config.get('max_size_mb', 100)
                backup_count = type_config.get('backup_count', 5)
            else:
                type_config = logging_config.get('backend', {})
                log_file = type_config.get('file', './logs/backend.log')
                max_size_mb = type_config.get('max_size_mb', 100)
                backup_count = type_config.get('backup_count', 5)
            
            # Resolve relative paths relative to project root
            if not Path(log_file).is_absolute():
                log_file = str(config_file.parent / log_file)
            
            _setup_logging_from_config(log_level, log_file, max_size_mb, backup_count, log_type=log_type)
        else:
            # Fallback to defaults if config file not found
            default_file = './logs/backend.log' if log_type == 'backend' else './logs/frontend.log'
            _setup_logging_from_config('INFO', default_file, 100, 5, log_type=log_type)
    except Exception as e:
        # Fallback to defaults if there's any error
        import sys
        print(f'Warning: Failed to load logging config: {e}', file=sys.stderr)
        default_file = './logs/backend.log' if log_type == 'backend' else './logs/frontend.log'
        _setup_logging_from_config('INFO', default_file, 100, 5, log_type=log_type)


def get_logger(name, log_type='backend'):
    """
    Get a logger instance. If logging hasn't been initialized yet, initialize it standalone.
    
    Args:
        name: Logger name (usually __name__)
        log_type: Type of logger ('frontend' or 'backend'), defaults to 'backend'
        
    Returns:
        Logger instance
    """
    global _frontend_logging_initialized, _backend_logging_initialized
    
    # Determine which logger to use based on log_type
    if log_type == 'frontend':
        if not _frontend_logging_initialized:
            try:
                setup_logging_standalone(log_type='frontend')
            except Exception:
                # If that fails, at least ensure basic logging is available
                logging.basicConfig(
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                _frontend_logging_initialized = True
        # Return a child logger of the frontend logger
        return logging.getLogger(f'frontend.{name}')
    else:
        if not _backend_logging_initialized:
            try:
                setup_logging_standalone(log_type='backend')
            except Exception:
                # If that fails, at least ensure basic logging is available
                logging.basicConfig(
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                _backend_logging_initialized = True
        # Return a child logger of the backend logger
        return logging.getLogger(f'backend.{name}')

