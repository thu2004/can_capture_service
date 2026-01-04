"""
File operations
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.utils.logger import get_logger
from app.utils.validators import validate_filename

logger = get_logger(__name__, log_type='frontend')


class FileService:
    """Service for managing captured files"""
    
    def __init__(self, capture_dir: Path, metadata_dir: Path):
        """
        Initialize file service
        
        Args:
            capture_dir: Directory containing capture files
            metadata_dir: Directory containing metadata files
        """
        self.capture_dir = Path(capture_dir)
        self.metadata_dir = Path(metadata_dir)
        
        # Ensure directories exist
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
    
    def list_files(self, interface: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        List captured files with metadata
        
        Args:
            interface: Filter by interface name (optional)
            limit: Maximum number of files to return
            offset: Offset for pagination
            
        Returns:
            Dictionary with files list and metadata
        """
        files = []
        
        try:
            # Get all files in capture directory only
            if not self.capture_dir.exists():
                return {
                    'files': [],
                    'total': 0,
                    'limit': limit,
                    'offset': offset,
                    'count': 0
                }
            
            for file_path in self.capture_dir.iterdir():
                if file_path.is_file() and not file_path.name.startswith('.'):
                    # Get file metadata
                    file_info = self._get_file_info(file_path)
                    
                    # Filter by interface if specified
                    if interface and file_info.get('interface') != interface:
                        continue
                    
                    files.append(file_info)
            
            # Sort by creation time (newest first)
            files.sort(key=lambda x: x.get('created', ''), reverse=True)
            
            # Apply pagination
            total = len(files)
            files = files[offset:offset + limit]
            
            return {
                'files': files,
                'total': total,
                'limit': limit,
                'offset': offset,
                'count': len(files)
            }
            
        except Exception as e:
            logger.error(f'Error listing files: {e}')
            return {
                'files': [],
                'total': 0,
                'limit': limit,
                'offset': offset,
                'count': 0,
                'error': str(e)
            }
    
    def _get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """
        Get metadata for a file
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file metadata
        """
        stat = file_path.stat()
        size = stat.st_size
        created = datetime.fromtimestamp(stat.st_ctime)
        modified = datetime.fromtimestamp(stat.st_mtime)
        
        # Try to load metadata from JSON file
        metadata = self._load_file_metadata(file_path.name)
        
        # Extract interface from filename if possible
        interface = metadata.get('interface')
        if not interface:
            # Try to parse from filename: capture_<interface>_<timestamp>.log
            parts = file_path.stem.split('_')
            if len(parts) >= 2 and parts[0] == 'capture':
                interface = parts[1]
        
        # Calculate duration if available
        duration = None
        if metadata.get('start_time') and metadata.get('end_time'):
            start = datetime.fromisoformat(metadata['start_time'])
            end = datetime.fromisoformat(metadata['end_time'])
            duration = (end - start).total_seconds()
        elif metadata.get('start_time'):
            start = datetime.fromisoformat(metadata['start_time'])
            duration = (datetime.now() - start).total_seconds()
        
        return {
            'filename': file_path.name,
            'size': size,
            'size_mb': round(size / (1024 * 1024), 2),
            'created': created.isoformat(),
            'modified': modified.isoformat(),
            'interface': interface,
            'duration': duration,
            'message_count': metadata.get('message_count', 0),
            'format': metadata.get('format', 'log'),
            'session_id': metadata.get('session_id')
        }
    
    def _load_file_metadata(self, filename: str) -> Dict[str, Any]:
        """
        Load metadata for a file from JSON metadata file
        
        Args:
            filename: Name of the capture file
            
        Returns:
            Dictionary with metadata
        """
        # Look for metadata file with same base name
        base_name = Path(filename).stem
        metadata_file = self.metadata_dir / f"{base_name}.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f'Error loading metadata for {filename}: {e}')
        
        return {}
    
    def get_file_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific file
        
        Args:
            filename: Name of the file
            
        Returns:
            Dictionary with file info or None if not found
        """
        if not validate_filename(filename):
            return None
        
        file_path = self.capture_dir / filename
        
        if not file_path.exists() or not file_path.is_file():
            return None
        
        return self._get_file_info(file_path)
    
    def get_file_path(self, filename: str) -> Optional[Path]:
        """
        Get full path to a file
        
        Args:
            filename: Name of the file
            
        Returns:
            Path object or None if invalid/not found
        """
        if not validate_filename(filename):
            return None
        
        file_path = self.capture_dir / filename
        
        if not file_path.exists() or not file_path.is_file():
            return None
        
        # Security check: ensure file is within capture directory
        try:
            file_path.resolve().relative_to(self.capture_dir.resolve())
        except ValueError:
            logger.warning(f'Invalid file path: {filename}')
            return None
        
        return file_path
    
    def delete_file(self, filename: str) -> Dict[str, Any]:
        """
        Delete a captured file
        
        Args:
            filename: Name of the file to delete
            
        Returns:
            Dictionary with result
        """
        if not validate_filename(filename):
            return {
                'success': False,
                'error': 'Invalid filename'
            }
        
        # Only look for file in capture directory
        file_path = self.capture_dir / filename
        
        if not file_path.exists() or not file_path.is_file():
            return {
                'success': False,
                'error': 'File not found'
            }
        
        # Security check - ensure file is within capture directory
        try:
            # Ensure file is within capture directory
            file_path.resolve().relative_to(self.capture_dir.resolve())
        except ValueError:
            logger.warning(f'Invalid file path: {filename}')
            return {
                'success': False,
                'error': 'Invalid file path'
            }
        
        try:
            # Delete the file
            file_path.unlink()
            logger.info(f'Deleted file: {file_path}')
            
            # Try to delete associated metadata file
            base_name = Path(filename).stem
            metadata_file = self.metadata_dir / f"{base_name}.json"
            if metadata_file.exists():
                try:
                    metadata_file.unlink()
                    logger.info(f'Deleted metadata file: {metadata_file}')
                except Exception as e:
                    logger.debug(f'Could not delete metadata file: {e}')
            
            return {
                'success': True,
                'message': f'File {filename} deleted successfully',
                'filename': filename
            }
            
        except Exception as e:
            logger.error(f'Error deleting file {filename}: {e}')
            return {
                'success': False,
                'error': 'Failed to delete file',
                'message': str(e)
            }
    
    def get_disk_usage(self) -> Dict[str, Any]:
        """
        Get disk usage information
        
        Returns:
            Dictionary with disk usage stats
        """
        try:
            import shutil
            
            total, used, free = shutil.disk_usage(self.capture_dir)
            
            # Calculate capture directory size
            capture_size = sum(f.stat().st_size for f in self.capture_dir.rglob('*') if f.is_file())
            
            return {
                'total_bytes': total,
                'used_bytes': used,
                'free_bytes': free,
                'total_gb': round(total / (1024**3), 2),
                'used_gb': round(used / (1024**3), 2),
                'free_gb': round(free / (1024**3), 2),
                'usage_percent': round((used / total) * 100, 2),
                'capture_dir_size_bytes': capture_size,
                'capture_dir_size_gb': round(capture_size / (1024**3), 2)
            }
        except Exception as e:
            logger.error(f'Error getting disk usage: {e}')
            return {
                'error': str(e)
            }
