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
        logger.debug(f'Initializing CaptureService with capture_dir={capture_dir}, metadata_dir={metadata_dir}')
        self.capture_dir = Path(capture_dir)
        self.metadata_dir = Path(metadata_dir)
        self.default_rotation = default_rotation
        self.active_sessions: Dict[str, CaptureSession] = {}
        
        # Ensure directories exist
        logger.debug(f'Creating directories: {self.capture_dir}, {self.metadata_dir}')
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        logger.debug('Directories created/verified')
        
        # Load existing sessions from metadata files
        logger.debug('Loading existing sessions from metadata')
        self._load_sessions_from_metadata()
        logger.debug(f'Initialized CaptureService with {len(self.active_sessions)} existing sessions')
    
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
        logger.debug(f'Starting capture: interface={interface}, bitrate={bitrate}, output_file={output_file}, space_limit_mb={space_limit_mb}')
        
        # Validate interface
        if not validate_interface_name(interface):
            logger.warning(f'Invalid interface name: {interface}')
            return {
                'success': False,
                'error': f'Invalid interface name: {interface}'
            }
        logger.debug(f'Interface {interface} validation passed')
        
        # Check if interface is already capturing
        logger.debug(f'Checking for existing captures on interface {interface}')
        for session in self.active_sessions.values():
            if session.interface == interface and session.status == 'running':
                logger.warning(f'Interface {interface} is already being captured in session {session.session_id}')
                return {
                    'success': False,
                    'error': f'Interface {interface} is already being captured',
                    'session_id': session.session_id
                }
        logger.debug(f'No existing capture found for interface {interface}')
        
        # Generate output filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"capture_{interface}_{timestamp}.log"
            logger.debug(f'Generated output filename: {output_file}')
        else:
            logger.debug(f'Using provided output filename: {output_file}')
        
        # Use default rotation if not provided
        if not rotation:
            rotation = self.default_rotation.copy()
            logger.debug(f'Using default rotation config: {rotation}')
        else:
            logger.debug(f'Using provided rotation config: {rotation}')
        
        # Use default space limit if not provided
        if space_limit_mb is None:
            space_limit_mb = 100.0
            logger.debug(f'Using default space limit: {space_limit_mb} MB')
        else:
            logger.debug(f'Using provided space limit: {space_limit_mb} MB')
        
        # Create session
        logger.debug('Creating capture session')
        session = CaptureSession.create(
            interface=interface,
            output_file=output_file,
            bitrate=bitrate,
            space_limit_mb=space_limit_mb,
            rotation=rotation
        )
        logger.debug(f'Created session {session.session_id} with status {session.status}')
        
        try:
            # Prepare worker configuration
            logger.debug('Preparing worker configuration')
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
            logger.debug(f'Worker config: {json.dumps(worker_config, indent=2)}')
            
            # Get path to worker script
            worker_script = Path(__file__).parent.parent.parent / 'worker' / 'capture_worker.py'
            logger.debug(f'Worker script path: {worker_script} (exists: {worker_script.exists()})')
            
            # Start worker process
            config_json = json.dumps(worker_config)
            logger.debug(f'Starting worker process with config length: {len(config_json)} bytes')
            process = subprocess.Popen(
                [sys.executable, str(worker_script), config_json],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(Path(__file__).parent.parent.parent)
            )
            logger.debug(f'Worker process started with PID: {process.pid}')
            
            # Wait a moment to check if process started successfully
            import time
            time.sleep(0.5)
            
            # Check if process is still running
            poll_result = process.poll()
            logger.debug(f'Worker process poll result: {poll_result} (None means still running)')
            if poll_result is not None:
                # Process exited immediately - get error
                stdout, stderr = process.communicate()
                error_msg = stderr.decode('utf-8') if stderr else stdout.decode('utf-8')
                logger.error(f'Worker process failed to start: {error_msg}')
                logger.debug(f'Worker stdout: {stdout.decode("utf-8")[:500] if stdout else "None"}')
                logger.debug(f'Worker stderr: {error_msg[:500]}')
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
            logger.debug(f'Added session {session.session_id} to active_sessions (total: {len(self.active_sessions)})')
            
            # Save session metadata to file
            logger.debug(f'Saving session metadata for {session.session_id}')
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
            logger.error(f'Error starting capture: {e}', exc_info=True)
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
        logger.debug(f'Stopping capture session: {session_id}')
        
        # Load sessions first to ensure we have the latest
        logger.debug('Reloading sessions from metadata before stop')
        self._load_sessions_from_metadata()
        
        if session_id not in self.active_sessions:
            logger.warning(f'Session {session_id} not found in active_sessions')
            return {
                'success': False,
                'error': f'Session {session_id} not found'
            }
        
        session = self.active_sessions[session_id]
        logger.debug(f'Session {session_id} found: interface={session.interface}, status={session.status}, worker_pid={session.worker_pid}')
        
        if session.status != 'running':
            logger.warning(f'Session {session_id} is not running (status: {session.status})')
            return {
                'success': False,
                'error': f'Session {session_id} is not running (status: {session.status})'
            }
        
        try:
            # Send SIGTERM to worker process, then SIGKILL if needed
            worker_pid = session.worker_pid
            
            # If worker_pid is not set, try to find it by looking at running processes
            if not worker_pid:
                logger.warning(f'worker_pid not found in session metadata for {session_id}, searching for worker process')
                try:
                    # Use pgrep to find the worker process by session_id
                    result = subprocess.run(
                        ['pgrep', '-f', f'capture_worker.py.*{session_id}'],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        found_pid = int(result.stdout.strip().split('\n')[0])
                        logger.info(f'Found worker process PID {found_pid} for session {session_id} using pgrep')
                        worker_pid = found_pid
                        # Update session with found PID
                        session.worker_pid = worker_pid
                        self._save_session_metadata(session)
                except (subprocess.SubprocessError, ValueError, FileNotFoundError) as e:
                    logger.warning(f'Could not search for worker process: {e}')
            
            if worker_pid:
                logger.debug(f'Stopping worker process {worker_pid}')
                try:
                    import time
                    # Check if process exists
                    logger.debug(f'Checking if process {worker_pid} exists')
                    os.kill(worker_pid, 0)
                    logger.debug(f'Process {worker_pid} exists, sending SIGTERM')
                    # Process exists, send SIGTERM for graceful shutdown
                    os.kill(worker_pid, signal.SIGTERM)
                    logger.info(f'Sent SIGTERM to worker process {worker_pid}')
                    
                    # Wait for graceful shutdown (up to 3 seconds)
                    logger.debug('Waiting for graceful shutdown (max 3 seconds)')
                    for i in range(6):
                        time.sleep(0.5)
                        try:
                            os.kill(worker_pid, 0)
                            # Process still exists
                            logger.debug(f'Process {worker_pid} still running after {i+1} attempts')
                        except ProcessLookupError:
                            # Process terminated
                            logger.info(f'Worker process {worker_pid} terminated gracefully after {i*0.5} seconds')
                            break
                    else:
                        # Process still running after SIGTERM, force kill
                        logger.debug(f'Process {worker_pid} did not terminate gracefully, sending SIGKILL')
                        try:
                            os.kill(worker_pid, 0)
                            logger.warning(f'Worker process {worker_pid} did not terminate, sending SIGKILL')
                            os.kill(worker_pid, signal.SIGKILL)
                            time.sleep(0.5)
                            # Verify it's dead
                            try:
                                os.kill(worker_pid, 0)
                                logger.error(f'Worker process {worker_pid} still exists after SIGKILL')
                            except ProcessLookupError:
                                logger.info(f'Worker process {worker_pid} killed with SIGKILL')
                        except ProcessLookupError:
                            logger.debug(f'Process {worker_pid} already terminated')
                            pass  # Already terminated
                except ProcessLookupError:
                    logger.warning(f'Process {worker_pid} not found (may have already stopped)')
                except PermissionError:
                    logger.warning(f'Permission denied when stopping process {worker_pid}')
                except Exception as e:
                    logger.error(f'Error stopping process: {e}', exc_info=True)
            else:
                logger.warning(f'No worker_pid found for session {session_id} and could not locate worker process, skipping process termination')
            
            logger.debug(f'Updating session {session_id} status to stopped')
            session.status = 'stopped'
            session.stop_time = datetime.now()
            session.worker_pid = None  # Clear worker_pid when stopping
            
            # Update metadata file immediately to prevent reload from changing status
            logger.debug(f'Saving session metadata for stopped session {session_id}')
            self._save_session_metadata(session)
            
            # Also update the metadata file directly to ensure it's saved with stopped status
            # Clear worker_pid so reload doesn't think process is still running
            metadata_file = self.metadata_dir / f"{session_id}.json"
            logger.debug(f'Updating metadata file directly: {metadata_file}')
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
                    logger.error(f'Error updating metadata file directly: {e}', exc_info=True)
            
            # Remove stopped session from active_sessions to prevent it from being reloaded
            # This ensures the session won't be detected as running again
            if session_id in self.active_sessions:
                logger.debug(f'Removing session {session_id} from active_sessions')
                del self.active_sessions[session_id]
                logger.debug(f'Active sessions remaining: {len(self.active_sessions)}')
            
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
            except Exception:
                pass
            return {
                'success': False,
                'error': 'Failed to stop capture',
                'message': str(e)
            }
    
    def get_session(self, session_id: str) -> Optional[CaptureSession]:
        """Get session by ID"""
        logger.debug(f'Getting session: {session_id}')
        session = self.active_sessions.get(session_id)
        if session:
            logger.debug(f'Session {session_id} found: status={session.status}, interface={session.interface}')
        else:
            logger.debug(f'Session {session_id} not found in active_sessions')
        return session
    
    def list_sessions(self) -> List[CaptureSession]:
        """List all active sessions"""
        logger.debug('Listing sessions')
        # Reload sessions from metadata to get latest status
        self._load_sessions_from_metadata()
        # Return running, error, and recently stopped sessions (within last hour)
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(hours=1)
        logger.debug(f'Filtering sessions with cutoff time: {cutoff_time}')
        sessions = [s for s in self.active_sessions.values() 
                if s.status in ['running', 'error'] or 
                (s.status == 'stopped' and s.start_time > cutoff_time)]
        logger.debug(f'Found {len(sessions)} sessions to return (total in active_sessions: {len(self.active_sessions)})')
        return sessions
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a session"""
        logger.debug(f'Getting session status: {session_id}')
        session = self.get_session(session_id)
        if not session:
            logger.debug(f'Session {session_id} not found')
            return None
        
        # Try to load updated metadata
        metadata_file = self.metadata_dir / f"{session_id}.json"
        logger.debug(f'Loading metadata from: {metadata_file} (exists: {metadata_file.exists()})')
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                logger.debug(f'Loaded metadata for {session_id}: message_count={metadata.get("message_count")}, rotation_info={metadata.get("rotation_info", {})}')
                session.message_count = metadata.get('message_count', session.message_count)
                rotation_info = metadata.get('rotation_info', {})
                if rotation_info:
                    session.current_size_mb = rotation_info.get('current_size_mb', 0)
                    logger.debug(f'Updated session {session_id} size: {session.current_size_mb} MB')
                    # Update rotation info in session
                    if 'rotation' in session.__dict__:
                        session.rotation.update(rotation_info)
            except Exception as e:
                logger.debug(f'Error loading metadata: {e}', exc_info=True)
        
        status_dict = session.to_dict()
        logger.debug(f'Session {session_id} status: {status_dict}')
        return status_dict
    
    def cleanup_inactive_sessions(self, older_than_hours: int = 24, remove_all_errors: bool = False) -> Dict[str, Any]:
        """
        Clean up inactive (stopped/error) capture sessions
        
        Args:
            older_than_hours: Not used anymore - kept for API compatibility
            remove_all_errors: Not used anymore - kept for API compatibility
            
        Returns:
            Dictionary with cleanup results
        """
        logger.debug(f'Starting cleanup of inactive sessions (older_than_hours={older_than_hours}, remove_all_errors={remove_all_errors})')
        try:
            # Load all sessions
            self._load_sessions_from_metadata()
            logger.debug(f'Loaded {len(self.active_sessions)} sessions for cleanup check')
            
            removed_count = 0
            removed_sessions = []
            
            for session_id, session in list(self.active_sessions.items()):
                logger.debug(f'Checking session {session_id}: status={session.status}')
                # Remove all sessions except RUNNING ones
                if session.status != 'running':
                    logger.debug(f'Removing inactive session {session_id} (status: {session.status})')
                    # Remove from active sessions
                    del self.active_sessions[session_id]
                    
                    # Delete metadata file
                    metadata_file = self.metadata_dir / f"{session_id}.json"
                    if metadata_file.exists():
                        logger.debug(f'Deleting metadata file: {metadata_file}')
                        metadata_file.unlink()
                    else:
                        logger.debug(f'Metadata file not found: {metadata_file}')
                    
                    removed_count += 1
                    removed_sessions.append(session_id)
                    logger.info(f'Cleaned up inactive session: {session_id} (status: {session.status})')
                else:
                    logger.debug(f'Keeping running session {session_id}')
            
            logger.debug(f'Cleanup complete: removed {removed_count} sessions, {len(self.active_sessions)} remaining')
            return {
                'success': True,
                'removed_count': removed_count,
                'removed_sessions': removed_sessions,
                'message': f'Removed {removed_count} inactive session(s)'
            }
            
        except Exception as e:
            logger.error(f'Error cleaning up sessions: {e}', exc_info=True)
            return {
                'success': False,
                'error': 'Failed to cleanup sessions',
                'message': str(e)
            }
    
    def _load_sessions_from_metadata(self):
        """Load sessions from metadata files"""
        logger.debug(f'Loading sessions from metadata directory: {self.metadata_dir}')
        try:
            # Scan metadata directory for session files
            metadata_files = list(self.metadata_dir.glob('*.json'))
            logger.debug(f'Found {len(metadata_files)} metadata files')
            
            for metadata_file in metadata_files:
                logger.debug(f'Loading session from: {metadata_file}')
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    session_id = metadata.get('session_id')
                    if not session_id:
                        # Try to get from filename
                        session_id = metadata_file.stem
                        logger.debug(f'Session ID not in metadata, using filename: {session_id}')
                    
                    # Check if process is still running
                    status = metadata.get('status', 'stopped')
                    worker_pid = metadata.get('worker_pid')
                    logger.debug(f'Session {session_id}: status={status}, worker_pid={worker_pid}')
                    
                    # Don't reclassify stopped sessions - if it's marked as stopped, keep it stopped
                    # Only check running sessions to see if they crashed
                    # If status is already 'stopped', don't check process - keep it stopped
                    if status == 'stopped':
                        # Ensure worker_pid is cleared for stopped sessions
                        if worker_pid:
                            logger.debug(f'Clearing worker_pid for stopped session {session_id}')
                            metadata['worker_pid'] = None
                            with open(metadata_file, 'w') as f:
                                json.dump(metadata, f, indent=2)
                    elif status == 'running' and worker_pid:
                        # Check if process is still alive
                        logger.debug(f'Checking if worker process {worker_pid} is still running for session {session_id}')
                        try:
                            os.kill(worker_pid, 0)  # Check if process exists
                            # Process is still running, keep status as running
                            logger.debug(f'Worker process {worker_pid} is still running for session {session_id}')
                        except (OSError, ProcessLookupError):
                            # Process is dead - this means it crashed unexpectedly
                            logger.warning(f'Worker process {worker_pid} is dead for session {session_id}, marking as error')
                            # Only mark as error if it was actually running (not already stopped)
                            if metadata.get('status') == 'running':
                                status = 'error'
                                metadata['status'] = 'error'
                                metadata['worker_pid'] = None  # Clear worker_pid
                                if not metadata.get('error_message'):
                                    metadata['error_message'] = 'Worker process terminated unexpectedly'
                                with open(metadata_file, 'w') as f:
                                    json.dump(metadata, f, indent=2)
                                logger.debug(f'Updated metadata file for crashed session {session_id}')
                            # If status was already changed to 'stopped' by stop_capture(), keep it as stopped
                    
                    # Create or update session (load all sessions, filter in list_sessions)
                    logger.debug(f'Creating CaptureSession object for {session_id}')
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
                    logger.debug(f'Loaded session {session_id}: interface={session.interface}, status={session.status}, messages={session.message_count}')
                        
                except Exception as e:
                    logger.debug(f'Error loading session from {metadata_file}: {e}', exc_info=True)
            
            logger.debug(f'Loaded {len(self.active_sessions)} sessions from metadata')
        except Exception as e:
            logger.error(f'Error loading sessions from metadata: {e}', exc_info=True)
    
    def _save_session_metadata(self, session: CaptureSession):
        """Save session metadata to file"""
        metadata_file = self.metadata_dir / f"{session.session_id}.json"
        logger.debug(f'Saving session metadata for {session.session_id} to {metadata_file}')
        try:
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
            
            logger.debug(f'Metadata to save: status={metadata["status"]}, worker_pid={metadata["worker_pid"]}, message_count={metadata["message_count"]}')
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.debug(f'Successfully saved metadata for session {session.session_id}')
        except Exception as e:
            logger.error(f'Error saving session metadata: {e}', exc_info=True)
