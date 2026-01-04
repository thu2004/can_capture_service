"""
CAN message handler using candump CLI
"""
import subprocess
from typing import Optional
from app.utils.logger import get_logger

logger = get_logger(__name__, log_type='backend')


class CANHandler:
    """Handles CAN bus communication using candump"""
    
    def __init__(self, interface: str, bitrate: Optional[int] = None):
        """
        Initialize CAN handler
        
        Args:
            interface: CAN interface name (e.g., 'can0')
            bitrate: CAN bus bitrate (optional, interface should already be configured)
        """
        self.interface = interface
        self.bitrate = bitrate
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
    
    def connect(self) -> bool:
        """
        Connect to CAN bus using candump
        
        Returns:
            True if connected successfully
        """
        try:
            # Check if candump is available
            result = subprocess.run(['which', 'candump'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error('candump command not found. Please install can-utils package.')
                return False
            
            logger.info(f'Using candump for CAN interface {self.interface}')
            self.is_running = True
            return True
        except Exception as e:
            logger.error(f'Failed to initialize CAN handler: {e}')
            self.is_running = False
            return False
    
    def disconnect(self):
        """Disconnect from CAN bus"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info(f'Disconnected from CAN interface {self.interface}')
            except subprocess.TimeoutExpired:
                self.process.kill()
                logger.warning(f'Force killed candump process')
            except Exception as e:
                logger.error(f'Error disconnecting from CAN interface: {e}')
            finally:
                self.process = None
                self.is_running = False
    
    def start_capture(self, output_file: str) -> bool:
        """
        Start candump process to capture CAN messages
        
        Args:
            output_file: Path to output file
            
        Returns:
            True if started successfully
        """
        try:
            # Start candump process
            # candump format: (timestamp) interface id#data
            # -L: log file format on stdout (doesn't create separate log file)
            # -t z: timestamp format (relative time)
            self.process = subprocess.Popen(
                ['candump', '-L', '-t', 'z', self.interface],
                stdout=open(output_file, 'a'),
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.info(f'Started candump for {self.interface}, writing to {output_file}')
            return True
        except Exception as e:
            logger.error(f'Error starting candump: {e}')
            self.is_running = False
            return False
    
    def is_alive(self) -> bool:
        """Check if candump process is still running"""
        if self.process:
            return self.process.poll() is None
        return False
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
