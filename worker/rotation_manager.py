"""
Rotation and space limit management
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from app.utils.logger import get_logger

logger = get_logger(__name__, log_type='backend')


class RotationManager:
    """Manages file rotation and space limits for CAN captures"""
    
    def __init__(self, session_config: Dict[str, Any], capture_dir: Path):
        """
        Initialize rotation manager
        
        Args:
            session_config: Session configuration including rotation settings
            capture_dir: Directory where capture files are stored
        """
        self.session_config = session_config
        self.capture_dir = Path(capture_dir)
        self.rotation = session_config.get('rotation', {})
        self.space_limit_mb = session_config.get('space_limit_mb', 100.0)
        self.current_size_mb = 0.0
        self.current_file_index = self.rotation.get('current_file_index', 1)
        self.rotated_files = self.rotation.get('rotated_files', [])
        
    def check_rotation_needed(self, current_file_path: Path) -> Tuple[bool, str]:
        """
        Check if file rotation is needed
        
        Args:
            current_file_path: Path to current capture file
            
        Returns:
            Tuple of (needs_rotation, reason)
        """
        if not current_file_path.exists():
            return False, ""
        
        strategy = self.rotation.get('strategy', 'size')
        file_size_mb = current_file_path.stat().st_size / (1024 * 1024)
        
        # Check space limit
        if self.current_size_mb + file_size_mb >= self.space_limit_mb:
            return True, "space_limit_reached"
        
        # Strategy-specific checks
        if strategy == 'size':
            max_file_size_mb = self.rotation.get('max_file_size_mb', 50)
            if file_size_mb >= max_file_size_mb:
                return True, "file_size_limit"
        
        elif strategy == 'time':
            max_duration = self.rotation.get('max_file_duration_seconds', 3600)
            file_age = (datetime.now() - datetime.fromtimestamp(
                current_file_path.stat().st_mtime)).total_seconds()
            if file_age >= max_duration:
                return True, "file_duration_limit"
        
        elif strategy == 'count':
            max_files = self.rotation.get('max_files', 10)
            if len(self.rotated_files) + 1 >= max_files:
                return True, "file_count_limit"
        
        return False, ""
    
    def rotate_file(self, current_file_path: Path, base_name: str, extension: str) -> Optional[Path]:
        """
        Rotate the current file to a new file
        
        Args:
            current_file_path: Path to current file
            base_name: Base name for rotated files
            extension: File extension
            
        Returns:
            Path to new file, or None if rotation failed
        """
        rotation_action = self.rotation.get('rotation_action', 'rotate')
        
        if rotation_action == 'stop':
            logger.info(f'Rotation action is "stop", not rotating file')
            return None
        
        try:
            # Generate new filename
            new_filename = f"{base_name}_{self.current_file_index:03d}.{extension}"
            new_file_path = self.capture_dir / new_filename
            
            # If file exists, increment index
            while new_file_path.exists():
                self.current_file_index += 1
                new_filename = f"{base_name}_{self.current_file_index:03d}.{extension}"
                new_file_path = self.capture_dir / new_filename
            
            # Get current file size before rotation
            if current_file_path.exists():
                old_size = current_file_path.stat().st_size / (1024 * 1024)
                
                if rotation_action == 'delete_oldest':
                    # Delete oldest file if after rotation we would exceed max files
                    max_files = self.rotation.get('max_files', 10)
                    if len(self.rotated_files) + 1 >= max_files and self.rotated_files:
                        oldest_file = self.rotated_files[0]
                        oldest_path = self.capture_dir / oldest_file['filename']
                        if oldest_path.exists():
                            oldest_size = oldest_path.stat().st_size / (1024 * 1024)
                            oldest_path.unlink()
                            self.current_size_mb -= oldest_size
                            self.rotated_files.pop(0)
                            logger.info(f'Deleted oldest file: {oldest_file["filename"]}')
                
                # Rename current file to rotated name
                current_file_path.rename(new_file_path)
                logger.info(f'Rotated file: {current_file_path.name} -> {new_file_path.name}')
                
                # Track rotated file
                self.rotated_files.append({
                    'filename': new_filename,
                    'size_mb': old_size,
                    'rotated_at': datetime.now().isoformat()
                })
                self.current_size_mb += old_size
                
                # Update rotation metadata
                self.rotation['current_file_index'] = self.current_file_index
                self.rotation['total_files'] = len(self.rotated_files) + 1
                self.rotation['last_rotation_time'] = datetime.now().isoformat()
                self.rotation['rotated_files'] = self.rotated_files
            
            # Increment for next file
            self.current_file_index += 1
            
            # Create new empty file
            new_file_path.touch()
            return new_file_path
            
        except Exception as e:
            logger.error(f'Error rotating file: {e}')
            return None
    
    def update_size_tracking(self, file_path: Path):
        """
        Update size tracking for current file
        
        Args:
            file_path: Path to current capture file
        """
        # Calculate total size including rotated files
        total_rotated_size = sum(f.get('size_mb', 0) for f in self.rotated_files)
        if file_path.exists():
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            self.current_size_mb = total_rotated_size + file_size_mb
        else:
            # If file doesn't exist, only count rotated files
            self.current_size_mb = total_rotated_size
    
    def get_space_remaining_mb(self) -> float:
        """Get remaining space in MB"""
        return max(0, self.space_limit_mb - self.current_size_mb)
    
    def get_rotation_info(self) -> Dict[str, Any]:
        """Get current rotation information"""
        return {
            'current_file_index': self.current_file_index,
            'total_files': len(self.rotated_files) + 1,
            'current_size_mb': self.current_size_mb,
            'space_limit_mb': self.space_limit_mb,
            'space_remaining_mb': self.get_space_remaining_mb(),
            'rotated_files_count': len(self.rotated_files),
            'last_rotation_time': self.rotation.get('last_rotation_time')
        }
