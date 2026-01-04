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
        logger.debug(f'Initializing CANService with supported interfaces: {supported_interfaces}')
    
    def list_interfaces(self) -> List[CANInterface]:
        """
        List all available CAN interfaces
        
        Returns:
            List of CANInterface objects
        """
        logger.debug('Starting to list CAN interfaces')
        interfaces = []
        
        # Method 1: Check /sys/class/net for CAN interfaces
        net_path = Path('/sys/class/net')
        logger.debug(f'Checking /sys/class/net for CAN interfaces: {net_path.exists()}')
        if net_path.exists():
            for interface_dir in net_path.iterdir():
                interface_name = interface_dir.name
                logger.debug(f'Checking interface directory: {interface_name}')
                
                # Check if it's a CAN interface
                if self._is_can_interface(interface_dir):
                    logger.debug(f'Interface {interface_name} identified as CAN interface')
                    interface = self._get_interface_info(interface_name)
                    if interface:
                        interfaces.append(interface)
                        logger.debug(f'Added interface {interface_name} to list')
                    else:
                        logger.debug(f'Could not get info for interface {interface_name}')
        
        # Method 2: Use ip command to list CAN interfaces
        logger.debug('Attempting to use ip command to list CAN interfaces')
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', 'type', 'can'],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.debug(f'ip command return code: {result.returncode}')
            if result.returncode == 0:
                # Parse ip link output
                found_names = re.findall(r'^\d+:\s+(\w+):', result.stdout, re.MULTILINE)
                logger.debug(f'Found {len(found_names)} interfaces via ip command: {found_names}')
                for name in found_names:
                    # Check if we already have this interface
                    if not any(iface.name == name for iface in interfaces):
                        logger.debug(f'Getting info for interface {name} found via ip command')
                        interface = self._get_interface_info(name)
                        if interface:
                            interfaces.append(interface)
                            logger.debug(f'Added interface {name} from ip command to list')
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            logger.warning(f'Could not use ip command to list interfaces: {e}')
        
        # Sort by name
        interfaces.sort(key=lambda x: x.name)
        logger.info(f'Found {len(interfaces)} CAN interfaces: {[iface.name for iface in interfaces]}')
        
        return interfaces
    
    def _is_can_interface(self, interface_path: Path) -> bool:
        """
        Check if a network interface is a CAN interface
        
        Args:
            interface_path: Path to interface directory in /sys/class/net
            
        Returns:
            bool: True if CAN interface
        """
        name = interface_path.name
        logger.debug(f'Checking if {name} is a CAN interface')
        
        # Check for CAN-specific files
        can_type_file = interface_path / 'type'
        if can_type_file.exists():
            try:
                with open(can_type_file, 'r') as f:
                    interface_type = int(f.read().strip())
                    # CAN interface type is typically 280 (0x118)
                    is_can = interface_type == 280
                    logger.debug(f'Interface {name} type from file: {interface_type}, is CAN: {is_can}')
                    return is_can
            except (ValueError, IOError) as e:
                logger.debug(f'Error reading type file for {name}: {e}')
        
        # Fallback: check if name matches CAN interface pattern
        is_can_pattern = name.startswith('can') and name[3:].isdigit()
        logger.debug(f'Interface {name} pattern match (can*): {is_can_pattern}')
        return is_can_pattern
    
    def _get_interface_info(self, name: str) -> Optional[CANInterface]:
        """
        Get detailed information about a CAN interface
        
        Args:
            name: Interface name
            
        Returns:
            CANInterface object or None if not found/invalid
        """
        logger.debug(f'Getting interface info for {name}')
        if not validate_interface_name(name):
            logger.debug(f'Interface name {name} failed validation')
            return None
        
        try:
            # Get interface status
            logger.debug(f'Getting status for interface {name}')
            status = self._get_interface_status(name)
            logger.debug(f'Interface {name} status: {status}')
            
            # Get bitrate
            logger.debug(f'Getting bitrate for interface {name}')
            bitrate = self._get_interface_bitrate(name)
            logger.debug(f'Interface {name} bitrate: {bitrate}')
            
            # Get interface type
            logger.debug(f'Getting type for interface {name}')
            interface_type = self._get_interface_type(name)
            logger.debug(f'Interface {name} type: {interface_type}')
            
            # Get additional info
            logger.debug(f'Getting additional info for interface {name}')
            info = self._get_additional_info(name)
            logger.debug(f'Interface {name} additional info keys: {list(info.keys())}')
            
            interface = CANInterface(
                name=name,
                status=status,
                bitrate=bitrate,
                interface_type=interface_type,
                is_capturing=False,  # Will be updated by capture service
                active_session_id=None,  # Will be updated by capture service
                info=info
            )
            
            logger.debug(f'Successfully created CANInterface object for {name}')
            return interface
            
        except Exception as e:
            logger.error(f'Error getting info for interface {name}: {e}', exc_info=True)
            return None
    
    def _get_interface_status(self, name: str) -> str:
        """
        Get interface status (up/down)
        
        Args:
            name: Interface name
            
        Returns:
            Status string: 'up', 'down', or 'unknown'
        """
        logger.debug(f'Getting status for interface {name}')
        try:
            logger.debug(f'Running ip link show for {name}')
            result = subprocess.run(
                ['ip', 'link', 'show', name],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.debug(f'ip link show return code: {result.returncode}')
            
            if result.returncode == 0:
                # Check for UP state
                if 'state UP' in result.stdout:
                    logger.debug(f'Interface {name} is UP (from ip command)')
                    return 'up'
                elif 'state DOWN' in result.stdout:
                    logger.debug(f'Interface {name} is DOWN (from ip command)')
                    return 'down'
                else:
                    logger.debug(f'Interface {name} state not found in ip output: {result.stdout[:100]}')
            
            # Fallback: check /sys/class/net
            operstate_file = Path(f'/sys/class/net/{name}/operstate')
            logger.debug(f'Checking operstate file: {operstate_file} (exists: {operstate_file.exists()})')
            if operstate_file.exists():
                with open(operstate_file, 'r') as f:
                    state = f.read().strip().lower()
                    logger.debug(f'Interface {name} operstate from file: {state}')
                    if state == 'up':
                        return 'up'
                    elif state == 'down':
                        return 'down'
            
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError, IOError) as e:
            logger.debug(f'Could not get status for {name}: {e}', exc_info=True)
        
        logger.debug(f'Interface {name} status: unknown')
        return 'unknown'
    
    def _get_interface_bitrate(self, name: str) -> Optional[int]:
        """
        Get interface bitrate
        
        Args:
            name: Interface name
            
        Returns:
            Bitrate in bps or None
        """
        logger.debug(f'Getting bitrate for interface {name}')
        try:
            # Try to get bitrate from ip command
            logger.debug(f'Running ip -details link show for {name}')
            result = subprocess.run(
                ['ip', '-details', 'link', 'show', name],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.debug(f'ip -details link show return code: {result.returncode}')
            
            if result.returncode == 0:
                # Look for bitrate in output (e.g., "bitrate 500000")
                match = re.search(r'bitrate\s+(\d+)', result.stdout, re.IGNORECASE)
                if match:
                    bitrate = int(match.group(1))
                    logger.debug(f'Interface {name} bitrate from ip command: {bitrate} bps')
                    return bitrate
                else:
                    logger.debug(f'Bitrate not found in ip output for {name}')
            
            # Fallback: check /sys/class/net
            bitrate_file = Path(f'/sys/class/net/{name}/bitrate')
            logger.debug(f'Checking bitrate file: {bitrate_file} (exists: {bitrate_file.exists()})')
            if bitrate_file.exists():
                with open(bitrate_file, 'r') as f:
                    bitrate = int(f.read().strip())
                    logger.debug(f'Interface {name} bitrate from file: {bitrate} bps')
                    return bitrate
                    
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError, IOError, ValueError) as e:
            logger.debug(f'Could not get bitrate for {name}: {e}', exc_info=True)
        
        logger.debug(f'Could not determine bitrate for interface {name}')
        return None
    
    def _get_interface_type(self, name: str) -> Optional[str]:
        """
        Get interface type
        
        Args:
            name: Interface name
            
        Returns:
            Interface type string or None
        """
        logger.debug(f'Getting type for interface {name}')
        # Check if it's a virtual interface
        if name.startswith('vcan'):
            logger.debug(f'Interface {name} is virtual (vcan)')
            return 'virtual'
        
        # Check /sys/class/net for type
        type_file = Path(f'/sys/class/net/{name}/type')
        logger.debug(f'Checking type file: {type_file} (exists: {type_file.exists()})')
        if type_file.exists():
            try:
                with open(type_file, 'r') as f:
                    interface_type = int(f.read().strip())
                    logger.debug(f'Interface {name} type from file: {interface_type}')
                    if interface_type == 280:  # CAN type
                        logger.debug(f'Interface {name} is socketcan')
                        return 'socketcan'
            except (ValueError, IOError) as e:
                logger.debug(f'Error reading type file for {name}: {e}')
        
        logger.debug(f'Interface {name} defaulting to socketcan')
        return 'socketcan'  # Default assumption
    
    def _get_additional_info(self, name: str) -> Dict[str, Any]:
        """
        Get additional interface information
        
        Args:
            name: Interface name
            
        Returns:
            Dictionary with additional info
        """
        logger.debug(f'Getting additional info for interface {name}')
        info = {}
        
        try:
            # Get MTU
            mtu_file = Path(f'/sys/class/net/{name}/mtu')
            logger.debug(f'Checking MTU file: {mtu_file} (exists: {mtu_file.exists()})')
            if mtu_file.exists():
                with open(mtu_file, 'r') as f:
                    mtu = int(f.read().strip())
                    info['mtu'] = mtu
                    logger.debug(f'Interface {name} MTU: {mtu}')
            
            # Get statistics if available
            stats_path = Path(f'/sys/class/net/{name}/statistics')
            logger.debug(f'Checking statistics path: {stats_path} (exists: {stats_path.exists()})')
            if stats_path.exists():
                stats = {}
                stat_files = list(stats_path.iterdir())
                logger.debug(f'Found {len(stat_files)} statistic files for {name}')
                for stat_file in stat_files:
                    try:
                        with open(stat_file, 'r') as f:
                            stats[stat_file.name] = int(f.read().strip())
                    except (ValueError, IOError) as e:
                        logger.debug(f'Error reading stat file {stat_file.name} for {name}: {e}')
                if stats:
                    info['statistics'] = stats
                    logger.debug(f'Interface {name} statistics: {len(stats)} entries')
                    
        except (IOError, ValueError) as e:
            logger.debug(f'Could not get additional info for {name}: {e}', exc_info=True)
        
        logger.debug(f'Interface {name} additional info: {list(info.keys())}')
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
        logger.debug(f'Starting interface {name} with bitrate={bitrate}, default_bitrate={default_bitrate}')
        if not validate_interface_name(name):
            logger.warning(f'Invalid interface name: {name}')
            return {
                'success': False,
                'message': f'Invalid interface name: {name}'
            }
        
        try:
            # First check if interface exists
            logger.debug(f'Checking if interface {name} exists')
            interface = self.get_interface(name)
            if not interface:
                logger.warning(f'Interface {name} not found')
                return {
                    'success': False,
                    'message': f'Interface {name} not found'
                }
            logger.debug(f'Interface {name} exists, current status: {interface.status}')
            
            # Use provided bitrate or default
            use_bitrate = bitrate if bitrate else default_bitrate
            logger.debug(f'Using bitrate: {use_bitrate} bps for interface {name}')
            
            # First, ensure interface is down before configuring
            logger.debug(f'Bringing interface {name} down before configuration')
            down_result = subprocess.run(
                ['sudo', 'ip', 'link', 'set', name, 'down'],
                capture_output=True,
                text=True,
                timeout=10
            )
            logger.debug(f'ip link set {name} down return code: {down_result.returncode}')
            
            # Configure CAN interface type and bitrate
            # This must be done while interface is down
            logger.debug(f'Configuring interface {name} as CAN with bitrate {use_bitrate}')
            result = subprocess.run(
                ['sudo', 'ip', 'link', 'set', name, 'type', 'can', 'bitrate', str(use_bitrate)],
                capture_output=True,
                text=True,
                timeout=10
            )
            logger.debug(f'ip link set {name} type can bitrate return code: {result.returncode}')
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f'Failed to configure CAN interface {name}: {error_msg}')
                logger.debug(f'Configuration stderr: {result.stderr}')
                logger.debug(f'Configuration stdout: {result.stdout}')
                return {
                    'success': False,
                    'message': f'Failed to configure interface: {error_msg}'
                }
            logger.debug(f'Successfully configured interface {name}')
            
            # Bring interface up
            logger.debug(f'Bringing interface {name} up')
            result = subprocess.run(
                ['sudo', 'ip', 'link', 'set', name, 'up'],
                capture_output=True,
                text=True,
                timeout=10
            )
            logger.debug(f'ip link set {name} up return code: {result.returncode}')
            
            if result.returncode == 0:
                logger.info(f'Successfully started interface {name} with bitrate {use_bitrate} bps')
                return {
                    'success': True,
                    'message': f'Interface {name} started successfully',
                    'interface': name
                }
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f'Failed to start interface {name}: {error_msg}')
                logger.debug(f'Start stderr: {result.stderr}')
                logger.debug(f'Start stdout: {result.stdout}')
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
            logger.error(f'Error starting interface {name}: {e}', exc_info=True)
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
        logger.debug(f'Stopping interface {name}')
        if not validate_interface_name(name):
            logger.warning(f'Invalid interface name: {name}')
            return {
                'success': False,
                'message': f'Invalid interface name: {name}'
            }
        
        try:
            # Check if interface exists
            logger.debug(f'Checking if interface {name} exists')
            interface = self.get_interface(name)
            if not interface:
                logger.warning(f'Interface {name} not found')
                return {
                    'success': False,
                    'message': f'Interface {name} not found'
                }
            logger.debug(f'Interface {name} exists, current status: {interface.status}')
            
            # Bring interface down
            logger.debug(f'Bringing interface {name} down')
            result = subprocess.run(
                ['sudo', 'ip', 'link', 'set', name, 'down'],
                capture_output=True,
                text=True,
                timeout=10
            )
            logger.debug(f'ip link set {name} down return code: {result.returncode}')
            
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
                logger.debug(f'Stop stderr: {result.stderr}')
                logger.debug(f'Stop stdout: {result.stdout}')
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
            logger.error(f'Error stopping interface {name}: {e}', exc_info=True)
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
