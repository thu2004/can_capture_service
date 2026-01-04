"""
CAN interface operations
"""
import subprocess
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.models.interface import CANInterface
from app.utils.logger import get_logger
from app.utils.validators import validate_interface_name

logger = get_logger(__name__, log_type='frontend')


class CANService:
    """Service for managing CAN interfaces"""
    
    def __init__(self, supported_interfaces: List[str] = None):
        """
        Initialize CAN service
        
        Args:
            supported_interfaces: List of supported interface names
        """
        self.supported_interfaces = supported_interfaces or []
        self._interface_cache = {}
    
    def list_interfaces(self) -> List[CANInterface]:
        """
        List all available CAN interfaces
        
        Returns:
            List of CANInterface objects
        """
        interfaces = []
        
        # Method 1: Check /sys/class/net for CAN interfaces
        net_path = Path('/sys/class/net')
        if net_path.exists():
            for interface_dir in net_path.iterdir():
                interface_name = interface_dir.name
                
                # Check if it's a CAN interface
                if self._is_can_interface(interface_dir):
                    interface = self._get_interface_info(interface_name)
                    if interface:
                        interfaces.append(interface)
        
        # Method 2: Use ip command to list CAN interfaces
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', 'type', 'can'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse ip link output
                found_names = re.findall(r'^\d+:\s+(\w+):', result.stdout, re.MULTILINE)
                for name in found_names:
                    # Check if we already have this interface
                    if not any(iface.name == name for iface in interfaces):
                        interface = self._get_interface_info(name)
                        if interface:
                            interfaces.append(interface)
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            logger.warning(f'Could not use ip command to list interfaces: {e}')
        
        # Sort by name
        interfaces.sort(key=lambda x: x.name)
        
        return interfaces
    
    def _is_can_interface(self, interface_path: Path) -> bool:
        """
        Check if a network interface is a CAN interface
        
        Args:
            interface_path: Path to interface directory in /sys/class/net
            
        Returns:
            bool: True if CAN interface
        """
        # Check for CAN-specific files
        can_type_file = interface_path / 'type'
        if can_type_file.exists():
            try:
                with open(can_type_file, 'r') as f:
                    interface_type = int(f.read().strip())
                    # CAN interface type is typically 280 (0x118)
                    return interface_type == 280
            except (ValueError, IOError):
                pass
        
        # Fallback: check if name matches CAN interface pattern
        name = interface_path.name
        return name.startswith('can') and name[3:].isdigit()
    
    def _get_interface_info(self, name: str) -> Optional[CANInterface]:
        """
        Get detailed information about a CAN interface
        
        Args:
            name: Interface name
            
        Returns:
            CANInterface object or None if not found/invalid
        """
        if not validate_interface_name(name):
            return None
        
        try:
            # Get interface status
            status = self._get_interface_status(name)
            
            # Get bitrate
            bitrate = self._get_interface_bitrate(name)
            
            # Get interface type
            interface_type = self._get_interface_type(name)
            
            # Get additional info
            info = self._get_additional_info(name)
            
            interface = CANInterface(
                name=name,
                status=status,
                bitrate=bitrate,
                interface_type=interface_type,
                is_capturing=False,  # Will be updated by capture service
                active_session_id=None,  # Will be updated by capture service
                info=info
            )
            
            return interface
            
        except Exception as e:
            logger.error(f'Error getting info for interface {name}: {e}')
            return None
    
    def _get_interface_status(self, name: str) -> str:
        """
        Get interface status (up/down)
        
        Args:
            name: Interface name
            
        Returns:
            Status string: 'up', 'down', or 'unknown'
        """
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Check for UP state
                if 'state UP' in result.stdout:
                    return 'up'
                elif 'state DOWN' in result.stdout:
                    return 'down'
            
            # Fallback: check /sys/class/net
            operstate_file = Path(f'/sys/class/net/{name}/operstate')
            if operstate_file.exists():
                with open(operstate_file, 'r') as f:
                    state = f.read().strip().lower()
                    if state == 'up':
                        return 'up'
                    elif state == 'down':
                        return 'down'
            
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError, IOError) as e:
            logger.debug(f'Could not get status for {name}: {e}')
        
        return 'unknown'
    
    def _get_interface_bitrate(self, name: str) -> Optional[int]:
        """
        Get interface bitrate
        
        Args:
            name: Interface name
            
        Returns:
            Bitrate in bps or None
        """
        try:
            # Try to get bitrate from ip command
            result = subprocess.run(
                ['ip', '-details', 'link', 'show', name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Look for bitrate in output (e.g., "bitrate 500000")
                match = re.search(r'bitrate\s+(\d+)', result.stdout, re.IGNORECASE)
                if match:
                    return int(match.group(1))
            
            # Fallback: check /sys/class/net
            bitrate_file = Path(f'/sys/class/net/{name}/bitrate')
            if bitrate_file.exists():
                with open(bitrate_file, 'r') as f:
                    return int(f.read().strip())
                    
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError, IOError, ValueError) as e:
            logger.debug(f'Could not get bitrate for {name}: {e}')
        
        return None
    
    def _get_interface_type(self, name: str) -> Optional[str]:
        """
        Get interface type
        
        Args:
            name: Interface name
            
        Returns:
            Interface type string or None
        """
        # Check if it's a virtual interface
        if name.startswith('vcan'):
            return 'virtual'
        
        # Check /sys/class/net for type
        type_file = Path(f'/sys/class/net/{name}/type')
        if type_file.exists():
            try:
                with open(type_file, 'r') as f:
                    interface_type = int(f.read().strip())
                    if interface_type == 280:  # CAN type
                        return 'socketcan'
            except (ValueError, IOError):
                pass
        
        return 'socketcan'  # Default assumption
    
    def _get_additional_info(self, name: str) -> Dict[str, Any]:
        """
        Get additional interface information
        
        Args:
            name: Interface name
            
        Returns:
            Dictionary with additional info
        """
        info = {}
        
        try:
            # Get MTU
            mtu_file = Path(f'/sys/class/net/{name}/mtu')
            if mtu_file.exists():
                with open(mtu_file, 'r') as f:
                    info['mtu'] = int(f.read().strip())
            
            # Get statistics if available
            stats_path = Path(f'/sys/class/net/{name}/statistics')
            if stats_path.exists():
                stats = {}
                for stat_file in stats_path.iterdir():
                    try:
                        with open(stat_file, 'r') as f:
                            stats[stat_file.name] = int(f.read().strip())
                    except (ValueError, IOError):
                        pass
                if stats:
                    info['statistics'] = stats
                    
        except (IOError, ValueError) as e:
            logger.debug(f'Could not get additional info for {name}: {e}')
        
        return info
    
    def get_interface(self, name: str) -> Optional[CANInterface]:
        """
        Get a specific interface by name
        
        Args:
            name: Interface name
            
        Returns:
            CANInterface object or None if not found
        """
        if not validate_interface_name(name):
            return None
        
        return self._get_interface_info(name)
    
    def validate_interface(self, name: str) -> bool:
        """
        Validate if an interface exists and is accessible
        
        Args:
            name: Interface name
            
        Returns:
            bool: True if valid and accessible
        """
        if not validate_interface_name(name):
            return False
        
        interface = self.get_interface(name)
        return interface is not None
    
    def start_interface(self, name: str, bitrate: Optional[int] = None, default_bitrate: int = 500000) -> Dict[str, Any]:
        """
        Start/bring up a CAN interface
        
        Args:
            name: Interface name
            bitrate: Optional bitrate to set (in bps)
            default_bitrate: Default bitrate to use if not provided (default: 500000)
            
        Returns:
            Dictionary with result status and message
        """
        if not validate_interface_name(name):
            return {
                'success': False,
                'message': f'Invalid interface name: {name}'
            }
        
        try:
            # First check if interface exists
            interface = self.get_interface(name)
            if not interface:
                return {
                    'success': False,
                    'message': f'Interface {name} not found'
                }
            
            # Use provided bitrate or default
            use_bitrate = bitrate if bitrate else default_bitrate
            
            # First, ensure interface is down before configuring
            subprocess.run(
                ['sudo', 'ip', 'link', 'set', name, 'down'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Configure CAN interface type and bitrate
            # This must be done while interface is down
            result = subprocess.run(
                ['sudo', 'ip', 'link', 'set', name, 'type', 'can', 'bitrate', str(use_bitrate)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f'Failed to configure CAN interface {name}: {error_msg}')
                return {
                    'success': False,
                    'message': f'Failed to configure interface: {error_msg}'
                }
            
            # Bring interface up
            result = subprocess.run(
                ['sudo', 'ip', 'link', 'set', name, 'up'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f'Successfully started interface {name}')
                return {
                    'success': True,
                    'message': f'Interface {name} started successfully',
                    'interface': name
                }
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f'Failed to start interface {name}: {error_msg}')
                return {
                    'success': False,
                    'message': f'Failed to start interface: {error_msg}'
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f'Timeout starting interface {name}')
            return {
                'success': False,
                'message': 'Timeout while starting interface'
            }
        except Exception as e:
            logger.error(f'Error starting interface {name}: {e}')
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def stop_interface(self, name: str) -> Dict[str, Any]:
        """
        Stop/bring down a CAN interface
        
        Args:
            name: Interface name
            
        Returns:
            Dictionary with result status and message
        """
        if not validate_interface_name(name):
            return {
                'success': False,
                'message': f'Invalid interface name: {name}'
            }
        
        try:
            # Check if interface exists
            interface = self.get_interface(name)
            if not interface:
                return {
                    'success': False,
                    'message': f'Interface {name} not found'
                }
            
            # Bring interface down
            result = subprocess.run(
                ['sudo', 'ip', 'link', 'set', name, 'down'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f'Successfully stopped interface {name}')
                return {
                    'success': True,
                    'message': f'Interface {name} stopped successfully',
                    'interface': name
                }
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f'Failed to stop interface {name}: {error_msg}')
                return {
                    'success': False,
                    'message': f'Failed to stop interface: {error_msg}'
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f'Timeout stopping interface {name}')
            return {
                'success': False,
                'message': 'Timeout while stopping interface'
            }
        except Exception as e:
            logger.error(f'Error stopping interface {name}: {e}')
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
