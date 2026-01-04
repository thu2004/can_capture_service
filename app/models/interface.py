"""
CAN interface model
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class CANInterface:
    """CAN interface data model"""
    name: str
    status: str  # 'up', 'down', 'unknown'
    bitrate: Optional[int] = None
    interface_type: Optional[str] = None  # 'socketcan', 'virtual', etc.
    is_capturing: bool = False
    active_session_id: Optional[str] = None
    last_seen: Optional[datetime] = None
    info: Optional[Dict[str, Any]] = None
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'status': self.status,
            'bitrate': self.bitrate,
            'type': self.interface_type,
            'is_capturing': self.is_capturing,
            'active_session_id': self.active_session_id,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'info': self.info or {}
        }
