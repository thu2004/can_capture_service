"""
Configuration management for CAN Capture Service
"""
import os
import yaml
from pathlib import Path


class Config:
    """Application configuration"""
    
    # Base directory
    BASE_DIR = Path(__file__).parent.parent
    
    # Load configuration from YAML file
    CONFIG_FILE = BASE_DIR / 'config.yaml'
    
    # Load YAML config once at class definition
    _config_data = None
    
    @classmethod
    def _load_config(cls):
        """Load configuration from YAML file"""
        if cls._config_data is None:
            with open(cls.CONFIG_FILE, 'r') as f:
                cls._config_data = yaml.safe_load(f)
        return cls._config_data
    
    @classmethod
    def init_app(cls, app):
        """Initialize Flask app with configuration"""
        config_data = cls._load_config()
        
        # Server configuration
        server = config_data.get('server', {})
        app.config['HOST'] = server.get('host', '0.0.0.0')
        app.config['PORT'] = server.get('port', 5000)
        app.config['DEBUG'] = server.get('debug', False)
        
        # Storage configuration
        storage = config_data.get('storage', {})
        app.config['CAPTURE_DIR'] = cls.BASE_DIR / storage.get('capture_dir', './storage/captures')
        app.config['METADATA_DIR'] = cls.BASE_DIR / storage.get('metadata_dir', './storage/metadata')
        app.config['MAX_FILE_SIZE_MB'] = storage.get('max_file_size_mb', 1000)
        app.config['CLEANUP_OLD_FILES_DAYS'] = storage.get('cleanup_old_files_days', 30)
        app.config['DEFAULT_SPACE_LIMIT_MB'] = storage.get('default_space_limit_mb', 100)
        app.config['GLOBAL_SPACE_LIMIT_MB'] = storage.get('global_space_limit_mb', 10000)
        app.config['ENABLE_SPACE_MONITORING'] = storage.get('enable_space_monitoring', True)
        
        # CAN configuration
        can = config_data.get('can', {})
        app.config['DEFAULT_BITRATE'] = can.get('default_bitrate', 500000)
        app.config['SUPPORTED_INTERFACES'] = can.get('supported_interfaces', ['can0', 'can1', 'vcan0'])
        app.config['CAPTURE_FORMAT'] = can.get('capture_format', 'log')
        app.config['DEFAULT_ROTATION'] = can.get('default_rotation', {
            'strategy': 'size',
            'max_file_size_mb': 50,
            'max_file_duration_seconds': 3600,
            'max_files': 10,
            'rotation_action': 'rotate'
        })
        
        # Logging configuration
        logging = config_data.get('logging', {})
        app.config['LOG_LEVEL'] = logging.get('level', 'INFO')
        
        # Frontend logging configuration
        frontend_logging = logging.get('frontend', {})
        app.config['LOG_FILE'] = cls.BASE_DIR / frontend_logging.get('file', './logs/frontend.log')
        app.config['LOG_MAX_SIZE_MB'] = frontend_logging.get('max_size_mb', 100)
        app.config['LOG_BACKUP_COUNT'] = frontend_logging.get('backup_count', 5)
        
        # Backend logging configuration (for reference in API)
        backend_logging = logging.get('backend', {})
        app.config['BACKEND_LOG_FILE'] = cls.BASE_DIR / backend_logging.get('file', './logs/backend.log')
        
        # Flask configuration
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
        app.config['JSON_SORT_KEYS'] = False

