"""
Input validation utilities
"""
import re
from pathlib import Path


def validate_interface_name(name):
    """
    Validate CAN interface name
    
    Args:
        name: Interface name to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not name or not isinstance(name, str):
        return False
    
    # CAN interface names are typically: can0, can1, vcan0, etc.
    pattern = r'^[a-z][a-z0-9]*\d+$'
    return bool(re.match(pattern, name))


def validate_filename(filename):
    """
    Validate filename to prevent path traversal
    
    Args:
        filename: Filename to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not filename or not isinstance(filename, str):
        return False
    
    # Check for path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    
    # Check for valid filename characters
    try:
        Path(filename).name == filename
        return True
    except (ValueError, OSError):
        return False


def validate_bitrate(bitrate):
    """
    Validate CAN bitrate
    
    Args:
        bitrate: Bitrate value to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(bitrate, int):
        return False
    
    # Common CAN bitrates: 10000, 20000, 50000, 100000, 125000, 250000, 500000, 800000, 1000000
    valid_bitrates = [10000, 20000, 50000, 100000, 125000, 250000, 500000, 800000, 1000000]
    return bitrate in valid_bitrates


def validate_space_limit(limit_mb):
    """
    Validate space limit in MB
    
    Args:
        limit_mb: Space limit in MB
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(limit_mb, (int, float)):
        return False
    
    return 0 < limit_mb <= 100000  # Max 100GB


def sanitize_string(value):
    """
    Sanitize string input to prevent XSS
    
    Args:
        value: String to sanitize
        
    Returns:
        str: Sanitized string
    """
    if not isinstance(value, str):
        return str(value)
    
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&']
    for char in dangerous_chars:
        value = value.replace(char, '')
    
    return value.strip()

