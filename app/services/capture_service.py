"""
Capture management
"""
import subprocess
import json
import os
import sys
import signal
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.models.session import CaptureSession
from app.utils.logger import get_logger
from app.utils.validators import validate_interface_name

logger = get_logger(__name__, log_type='frontend')


class CaptureService:
    """Service for managing CAN capture sessions"""
    
    def __init__(self, capture_dir: Path, metadata_dir: Path, default_rotation: Dict[str, Any]):
        """
        Initialize capture service
        
        Args:
            capture_dir: Directory for capture files
            metadata_dir: Directory for metadata files
            default_rotation: Default rotation configuration
        """
        self.capture_dir = Path(capture_dir)
        self.metadata_dir = Path(metadata_dir)
        self.default_rotation = default_rotation
        self.active_sessions: Dict[str, CaptureSession] = {}
        
        # Ensure directories exist
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing sessions from metadata files
        self._load_sessions_from_metadata()
    
    def start_capture(self, interface: str, bitrate: Optional[int] = None,
                     output_file: Optional[str] = None, space_limit_mb: Optional[float] = None,
                     rotation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Start a new capture session
        
        Args:
            interface: CAN interface name
            bitrate: CAN bitrate (optional)
            output_file: Output filename (auto-generated if not provided)
            space_limit_mb: Space limit in MB
            rotation: Rotation configuration
            
        Returns:
            Dictionary with session info or error
        """
        # Validate interface
        if not validate_interface_name(interface):
            return {
                'success': False,
                'error': f'Invalid interface name: {interface}'
            }
        
        # Check if interface is already capturing
        for session in self.active_sessions.values():
            if session.interface == interface and session.status == 'running':
                return {
                    'success': False,
                    'error': f'Interface {interface} is already being captured',
                    'session_id': session.session_id
                }
        
        # Generate output filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"capture_{interface}_{timestamp}.log"
        
        # Use default rotation if not provided
        if not rotation:
            rotation = self.default_rotation.copy()
        
        # Use default space limit if not provided
        if space_limit_mb is None:
            space_limit_mb = 100.0
        
        # Create session
        session = CaptureSession.create(
            interface=interface,
            output_file=output_file,
            bitrate=bitrate,
            space_limit_mb=space_limit_mb,
            rotation=rotation
        )
        
        try:
            # Prepare worker configuration
            worker_config = {
                'session_id': session.session_id,
                'interface': interface,
                'bitrate': bitrate,
                'output_file': output_file,
                'space_limit_mb': space_limit_mb,
                'rotation': rotation,
                'capture_dir': str(self.capture_dir),
                'metadata_dir': str(self.metadata_dir)
            }
            
            # Get path to worker script
            worker_script = Path(__file__).parent.parent.parent / 'worker' / 'capture_worker.py'
            
            # Start worker process
            config_json = json.dumps(worker_config)
            process = subprocess.Popen(
                [sys.executable, str(worker_script), config_json],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(Path(__file__).parent.parent.parent)
            )
            
            # Wait a moment to check if process started successfully
            import time
            time.sleep(0.5)
            
            # Check if process is still running
            if process.poll() is not None:
                # Process exited immediately - get error
                stdout, stderr = process.communicate()
                error_msg = stderr.decode('utf-8') if stderr else stdout.decode('utf-8')
                logger.error(f'Worker process failed to start: {error_msg}')
                session.status = 'error'
                session.error_message = error_msg[:200]  # Truncate long errors
                self._save_session_metadata(session)
                return {
                    'success': False,
                    'error': 'Failed to start capture worker',
                    'message': error_msg[:200]
                }
            
            session.worker_pid = process.pid
            self.active_sessions[session.session_id] = session
            
            # Save session metadata to file
            self._save_session_metadata(session)
            
            logger.info(f'Started capture session {session.session_id} on {interface}')
            
            return {
                'success': True,
                'session_id': session.session_id,
                'interface': interface,
                'status': 'running',
                'output_file': output_file,
                'start_time': session.start_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error starting capture: {e}')
            session.status = 'error'
            session.error_message = str(e)
            return {
                'success': False,
                'error': 'Failed to start capture',
                'message': str(e)
            }
    
    def stop_capture(self, session_id: str) -> Dict[str, Any]:
        """
        Stop a capture session
        
        Args:
            session_id: Session ID to stop
            
        Returns:
            Dictionary with result
        """
        # Load sessions first to ensure we have the latest
        self._load_sessions_from_metadata()
        
        if session_id not in self.active_sessions:
            return {
                'success': False,
                'error': f'Session {session_id} not found'
            }
        
        session = self.active_sessions[session_id]
        
        if session.status != 'running':
            return {
                'success': False,
                'error': f'Session {session_id} is not running (status: {session.status})'
            }
        
        try:
            # Send SIGTERM to worker process, then SIGKILL if needed
            if session.worker_pid:
                try:
                    import time
                    # Check if process exists
                    os.kill(session.worker_pid, 0)
                    # Process exists, send SIGTERM for graceful shutdown
                    os.kill(session.worker_pid, signal.SIGTERM)
                    logger.info(f'Sent SIGTERM to worker process {session.worker_pid}')
                    
                    # Wait for graceful shutdown (up to 3 seconds)
                    for i in range(6):
                        time.sleep(0.5)
                        try:
                            os.kill(session.worker_pid, 0)
                            # Process still exists
                        except ProcessLookupError:
                            # Process terminated
                            logger.info(f'Worker process {session.worker_pid} terminated gracefully')
                            break
                    else:
                        # Process still running after SIGTERM, force kill
                        try:
                            os.kill(session.worker_pid, 0)
                            logger.warning(f'Worker process {session.worker_pid} did not terminate, sending SIGKILL')
                            os.kill(session.worker_pid, signal.SIGKILL)
                            time.sleep(0.5)
                            # Verify it's dead
                            try:
                                os.kill(session.worker_pid, 0)
                                logger.error(f'Worker process {session.worker_pid} still exists after SIGKILL')
                            except ProcessLookupError:
                                logger.info(f'Worker process {session.worker_pid} killed with SIGKILL')
                        except ProcessLookupError:
                            pass  # Already terminated
                except ProcessLookupError:
                    logger.warning(f'Process {session.worker_pid} not found (may have already stopped)')
                except PermissionError:
                    logger.warning(f'Permission denied when stopping process {session.worker_pid}')
                except Exception as e:
                    logger.error(f'Error stopping process: {e}')
            
            session.status = 'stopped'
            session.stop_time = datetime.now()
            session.worker_pid = None  # Clear worker_pid when stopping
            
            # Update metadata file immediately to prevent reload from changing status
            self._save_session_metadata(session)
            
            # Also update the metadata file directly to ensure it's saved with stopped status
            # Clear worker_pid so reload doesn't think process is still running
            metadata_file = self.metadata_dir / f"{session_id}.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    metadata['status'] = 'stopped'
                    metadata['end_time'] = session.stop_time.isoformat()
                    metadata['worker_pid'] = None  # Clear worker_pid so reload doesn't check for process
                    # Remove error_message if it exists (since this is a clean stop)
                    if 'error_message' in metadata:
                        del metadata['error_message']
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata, f, indent=2)
                    logger.debug(f'Updated metadata file for stopped session: {session_id}')
                except Exception as e:
                    logger.error(f'Error updating metadata file directly: {e}')
            
            # Remove stopped session from active_sessions to prevent it from being reloaded
            # This ensures the session won't be detected as running again
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            logger.info(f'Stopped capture session {session_id}')
            
            return {
                'success': True,
                'session_id': session_id,
                'message': 'Capture stopped successfully'
            }
            
        except Exception as e:
            logger.error(f'Error stopping capture: {e}')
            # Still mark as stopped even if there was an error
            try:
                session.status = 'stopped'
                session.stop_time = datetime.now()
                self._save_session_metadata(session)
            except:
                pass
            return {
                'success': False,
                'error': 'Failed to stop capture',
                'message': str(e)
            }
    
    def get_session(self, session_id: str) -> Optional[CaptureSession]:
        """Get session by ID"""
        return self.active_sessions.get(session_id)
    
    def list_sessions(self) -> List[CaptureSession]:
        """List all active sessions"""
        # Reload sessions from metadata to get latest status
        self._load_sessions_from_metadata()
        # Return running, error, and recently stopped sessions (within last hour)
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(hours=1)
        return [s for s in self.active_sessions.values() 
                if s.status in ['running', 'error'] or 
                (s.status == 'stopped' and s.start_time > cutoff_time)]
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a session"""
        session = self.get_session(session_id)
        if not session:
            return None
        
        # Try to load updated metadata
        metadata_file = self.metadata_dir / f"{session_id}.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    session.message_count = metadata.get('message_count', session.message_count)
                    rotation_info = metadata.get('rotation_info', {})
                    if rotation_info:
                        session.current_size_mb = rotation_info.get('current_size_mb', 0)
                        # Update rotation info in session
                        if 'rotation' in session.__dict__:
                            session.rotation.update(rotation_info)
            except Exception as e:
                logger.debug(f'Error loading metadata: {e}')
        
        return session.to_dict()
    
    def cleanup_inactive_sessions(self, older_than_hours: int = 24, remove_all_errors: bool = False) -> Dict[str, Any]:
        """
        Clean up inactive (stopped/error) capture sessions
        
        Args:
            older_than_hours: Not used anymore - kept for API compatibility
            remove_all_errors: Not used anymore - kept for API compatibility
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            # Load all sessions
            self._load_sessions_from_metadata()
            
            removed_count = 0
            removed_sessions = []
            
            for session_id, session in list(self.active_sessions.items()):
                # Remove all sessions except RUNNING ones
                if session.status != 'running':
                    # Remove from active sessions
                    del self.active_sessions[session_id]
                    
                    # Delete metadata file
                    metadata_file = self.metadata_dir / f"{session_id}.json"
                    if metadata_file.exists():
                        metadata_file.unlink()
                    
                    removed_count += 1
                    removed_sessions.append(session_id)
                    logger.info(f'Cleaned up inactive session: {session_id} (status: {session.status})')
            
            return {
                'success': True,
                'removed_count': removed_count,
                'removed_sessions': removed_sessions,
                'message': f'Removed {removed_count} inactive session(s)'
            }
            
        except Exception as e:
            logger.error(f'Error cleaning up sessions: {e}')
            return {
                'success': False,
                'error': 'Failed to cleanup sessions',
                'message': str(e)
            }
    
    def _load_sessions_from_metadata(self):
        """Load sessions from metadata files"""
        try:
            # Scan metadata directory for session files
            for metadata_file in self.metadata_dir.glob('*.json'):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    session_id = metadata.get('session_id')
                    if not session_id:
                        # Try to get from filename
                        session_id = metadata_file.stem
                    
                    # Check if process is still running
                    status = metadata.get('status', 'stopped')
                    worker_pid = metadata.get('worker_pid')
                    start_time_str = metadata.get('start_time')
                    
                    # Don't reclassify stopped sessions - if it's marked as stopped, keep it stopped
                    # Only check running sessions to see if they crashed
                    # If status is already 'stopped', don't check process - keep it stopped
                    if status == 'stopped':
                        # Ensure worker_pid is cleared for stopped sessions
                        if worker_pid:
                            metadata['worker_pid'] = None
                            with open(metadata_file, 'w') as f:
                                json.dump(metadata, f, indent=2)
                    elif status == 'running' and worker_pid:
                        # Check if process is still alive
                        try:
                            os.kill(worker_pid, 0)  # Check if process exists
                            # Process is still running, keep status as running
                        except (OSError, ProcessLookupError):
                            # Process is dead - this means it crashed unexpectedly
                            # Only mark as error if it was actually running (not already stopped)
                            if metadata.get('status') == 'running':
                                status = 'error'
                                metadata['status'] = 'error'
                                metadata['worker_pid'] = None  # Clear worker_pid
                                if not metadata.get('error_message'):
                                    metadata['error_message'] = 'Worker process terminated unexpectedly'
                                with open(metadata_file, 'w') as f:
                                    json.dump(metadata, f, indent=2)
                            # If status was already changed to 'stopped' by stop_capture(), keep it as stopped
                    
                    # Create or update session (load all sessions, filter in list_sessions)
                    session = CaptureSession(
                        session_id=session_id,
                        interface=metadata.get('interface', 'unknown'),
                        start_time=datetime.fromisoformat(metadata.get('start_time', datetime.now().isoformat())),
                        status=status,
                        output_file=metadata.get('current_file', metadata.get('output_file', 'unknown')),
                        message_count=metadata.get('message_count', 0),
                        bitrate=metadata.get('bitrate'),
                        filters=metadata.get('filters', []),
                        space_limit_mb=metadata.get('space_limit_mb', 100.0),
                        current_size_mb=metadata.get('rotation_info', {}).get('current_size_mb', 0.0),
                        rotation=metadata.get('rotation', {}),
                        worker_pid=worker_pid,
                        error_message=metadata.get('error_message')
                    )
                    self.active_sessions[session_id] = session
                        
                except Exception as e:
                    logger.debug(f'Error loading session from {metadata_file}: {e}')
        except Exception as e:
            logger.error(f'Error loading sessions from metadata: {e}')
    
    def _save_session_metadata(self, session: CaptureSession):
        """Save session metadata to file"""
        try:
            metadata_file = self.metadata_dir / f"{session.session_id}.json"
            metadata = {
                'session_id': session.session_id,
                'interface': session.interface,
                'status': session.status,
                'output_file': session.output_file,
                'current_file': session.output_file,
                'message_count': session.message_count,
                'bitrate': session.bitrate,
                'filters': session.filters,
                'space_limit_mb': session.space_limit_mb,
                'start_time': session.start_time.isoformat(),
                'worker_pid': session.worker_pid,
                'rotation': session.rotation,
                'rotation_info': {
                    'current_size_mb': session.current_size_mb,
                    'current_file_index': session.rotation.get('current_file_index', 1),
                    'total_files': session.rotation.get('total_files', 1)
                }
            }
            
            if session.stop_time:
                metadata['end_time'] = session.stop_time.isoformat()
            
            if session.error_message:
                metadata['error_message'] = session.error_message
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f'Error saving session metadata: {e}')
