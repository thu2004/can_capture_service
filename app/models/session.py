"""
Capture session model
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path


@dataclass
class CaptureSession:
    """CAN capture session data model"""
    session_id: str
    interface: str
    start_time: datetime
    status: str  # 'running', 'stopped', 'error'
    output_file: str
    message_count: int = 0
    bitrate: Optional[int] = None
    filters: List[Dict[str, Any]] = field(default_factory=list)
    space_limit_mb: float = 100.0
    current_size_mb: float = 0.0
    rotation: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    stop_time: Optional[datetime] = None
    worker_pid: Optional[int] = None
    
    def __post_init__(self):
        """Initialize default rotation settings if not provided"""
        if not self.rotation:
            self.rotation = {
                'strategy': 'size',
                'max_file_size_mb': 50,
                'max_file_duration_seconds': 3600,
                'max_files': 10,
                'rotation_action': 'rotate',
                'current_file_index': 1,
                'total_files': 1,
                'last_rotation_time': None,
                'rotated_files': []
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'session_id': self.session_id,
            'interface': self.interface,
            'start_time': self.start_time.isoformat(),
            'status': self.status,
            'output_file': self.output_file,
            'message_count': self.message_count,
            'bitrate': self.bitrate,
            'filters': self.filters,
            'space_limit_mb': self.space_limit_mb,
            'current_size_mb': self.current_size_mb,
            'rotation': self.rotation,
            'error_message': self.error_message,
            'stop_time': self.stop_time.isoformat() if self.stop_time else None,
            'worker_pid': self.worker_pid,
            'duration_seconds': (datetime.now() - self.start_time).total_seconds() if self.status == 'running' else None
        }
    
    @classmethod
    def create(cls, interface: str, output_file: str, bitrate: Optional[int] = None,
               space_limit_mb: float = 100.0, rotation: Optional[Dict[str, Any]] = None) -> 'CaptureSession':
        """Create a new capture session"""
        session_id = str(uuid.uuid4())
        return cls(
            session_id=session_id,
            interface=interface,
            start_time=datetime.now(),
            status='running',
            output_file=output_file,
            bitrate=bitrate,
            space_limit_mb=space_limit_mb,
            rotation=rotation or {}
        )
