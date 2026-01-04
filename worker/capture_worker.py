"""
Main worker process for CAN capture using candump
"""
import os
import sys
import signal
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from worker.rotation_manager import RotationManager  # noqa: E402
from app.utils.logger import setup_logging_standalone, get_logger  # noqa: E402

# Initialize logging before using logger (backend logger for workers)
# Detect test environment to avoid writing test logs to production log file
_is_test_env = (
    os.environ.get('PYTEST_CURRENT_TEST') is not None or
    'pytest' in sys.modules or
    'unittest' in sys.modules
)

if not _is_test_env:
    # Only setup logging in production - tests should mock this
    setup_logging_standalone(log_type='backend')
logger = get_logger(__name__, log_type='backend')


class CaptureWorker:
    """Worker process for capturing CAN messages using candump"""
    
    def __init__(self, session_config: Dict[str, Any], capture_dir: Path, metadata_dir: Path):
        """
        Initialize capture worker
        
        Args:
            session_config: Session configuration
            capture_dir: Directory for capture files
            metadata_dir: Directory for metadata files
        """
        self.session_config = session_config
        self.capture_dir = Path(capture_dir)
        self.metadata_dir = Path(metadata_dir)
        self.session_id = session_config['session_id']
        self.interface = session_config['interface']
        self.bitrate = session_config.get('bitrate')
        self.output_file = session_config['output_file']
        self.space_limit_mb = session_config.get('space_limit_mb', 100.0)
        self.rotation_config = session_config.get('rotation', {})
        
        self.rotation_manager: Optional[RotationManager] = None
        self.current_file: Optional[Path] = None
        self.candump_process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.should_stop = False
        self.message_count = 0
        self.start_time = datetime.now()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        logger.info(f'Received signal {signum}, stopping capture...')
        self.should_stop = True
    
    def _count_messages_in_file(self, file_path: Path) -> int:
        """
        Count messages in a candump log file
        
        Args:
            file_path: Path to log file
            
        Returns:
            Number of messages
        """
        try:
            if not file_path.exists():
                return 0
            # Count lines in file (each line is a CAN message from candump)
            with open(file_path, 'r') as f:
                return sum(1 for _ in f)
        except Exception as e:
            logger.debug(f'Error counting messages: {e}')
            return 0
    
    def _check_and_rotate(self):
        """Check if rotation is needed and perform it"""
        if not self.current_file or not self.rotation_manager:
            return
        
        needs_rotation, reason = self.rotation_manager.check_rotation_needed(self.current_file)
        
        if needs_rotation:
            logger.info(f'Rotation needed: {reason}')
            
            # Stop current candump process
            if self.candump_process:
                try:
                    self.candump_process.terminate()
                    self.candump_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.candump_process.kill()
                    self.candump_process.wait()
                except Exception as e:
                    logger.error(f'Error stopping candump during rotation: {e}')
                self.candump_process = None
            
            # Get base name and extension
            base_name = self.current_file.stem.split('_')[0] if '_' in self.current_file.stem else self.current_file.stem
            extension = self.current_file.suffix[1:] if self.current_file.suffix else 'log'
            
            # Rotate file
            new_file = self.rotation_manager.rotate_file(self.current_file, base_name, extension)
            
            if new_file:
                self.current_file = new_file
                try:
                    # Restart candump with new file
                    self.candump_process = subprocess.Popen(
                        ['candump', '-L', '-t', 'z', self.interface],
                        stdout=open(self.current_file, 'a'),
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    logger.info(f'Rotated to new file: {self.current_file.name}')
                except Exception as e:
                    logger.error(f'Failed to start candump with new file: {e}')
                    self.should_stop = True
            else:
                # Rotation action is 'stop' or rotation failed
                logger.info('Stopping capture due to rotation action')
                self.should_stop = True
    
    def _update_metadata(self):
        """Update session metadata file"""
        try:
            metadata_file = self.metadata_dir / f"{self.session_id}.json"
            metadata = {
                'session_id': self.session_id,
                'interface': self.interface,
                'status': 'running' if self.is_running else 'stopped',
                'message_count': self.message_count,
                'start_time': self.start_time.isoformat(),
                'current_file': str(self.current_file.name) if self.current_file else None,
                'rotation_info': self.rotation_manager.get_rotation_info() if self.rotation_manager else {}
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f'Error updating metadata: {e}')
    
    def start(self) -> bool:
        """
        Start capture worker using candump
        
        Returns:
            True if started successfully
        """
        try:
            # Check if candump is available
            result = subprocess.run(['which', 'candump'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error('candump command not found. Please install can-utils package.')
                return False
            
            # Initialize rotation manager
            session_config = {
                'rotation': self.rotation_config,
                'space_limit_mb': self.space_limit_mb
            }
            self.rotation_manager = RotationManager(session_config, self.capture_dir)
            
            # Create output file
            self.current_file = self.capture_dir / self.output_file
            self.current_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Start candump process
            # candump -L -t z interface > output_file
            # -L: log file format on stdout (doesn't create separate log file)
            # -t z: timestamp format (relative time with microseconds)
            try:
                output_file_handle = open(self.current_file, 'a')
                self.candump_process = subprocess.Popen(
                    ['candump', '-L', '-t', 'z', self.interface],
                    stdout=output_file_handle,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1  # Line buffered
                )
                
                # Wait a moment to check if candump started successfully
                time.sleep(0.2)
                
                # Check if process exited immediately (indicates error)
                if self.candump_process.poll() is not None:
                    stderr = ''
                    try:
                        if self.candump_process.stderr:
                            stderr = self.candump_process.stderr.read()
                    except Exception:
                        pass
                    
                    error_msg = f'candump failed to start: {stderr.strip() or "unknown error"}'
                    logger.error(error_msg)
                    output_file_handle.close()
                    self.candump_process = None
                    raise Exception(error_msg)
                
                self.is_running = True
                self.should_stop = False
                logger.info(f'Capture worker started for interface {self.interface}, output: {self.current_file}')
            except Exception as e:
                logger.error(f'Failed to start candump: {e}')
                if 'output_file_handle' in locals():
                    try:
                        output_file_handle.close()
                    except Exception:
                        pass
                raise
            
            # Monitor capture process
            rotation_check_interval = 5.0  # Check rotation every N seconds
            metadata_update_interval = 5.0  # Update metadata every N seconds
            last_rotation_check = time.time()
            last_metadata_update = time.time()
            
            while not self.should_stop and self.is_running:
                try:
                    # Check if candump process is still running
                    if self.candump_process and self.candump_process.poll() is not None:
                        # Process exited
                        stderr = ''
                        try:
                            if self.candump_process.stderr:
                                stderr = self.candump_process.stderr.read()
                        except Exception:
                            pass
                        
                        return_code = self.candump_process.returncode
                        logger.error(f'candump process exited unexpectedly with code {return_code}: {stderr}')
                        
                        # Update metadata with error status
                        self.is_running = False
                        self._update_metadata()
                        
                        # Don't break immediately - let the finally block handle cleanup
                        self.should_stop = True
                        break
                
                    # Check rotation periodically
                    current_time = time.time()
                    if current_time - last_rotation_check >= rotation_check_interval:
                        self._check_and_rotate()
                        if self.rotation_manager:
                            self.rotation_manager.update_size_tracking(self.current_file)
                        last_rotation_check = current_time
                    
                    # Update metadata periodically
                    if current_time - last_metadata_update >= metadata_update_interval:
                        # Count messages in file
                        self.message_count = self._count_messages_in_file(self.current_file)
                        self._update_metadata()
                        last_metadata_update = current_time
                    
                    # Sleep to avoid busy waiting
                    time.sleep(0.5)
                    
                except KeyboardInterrupt:
                    logger.info('Received keyboard interrupt')
                    self.should_stop = True
                    break
                except Exception as e:
                    logger.error(f'Error in capture loop: {e}', exc_info=True)
                    # Continue running unless it's a critical error
                    time.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f'Error in capture worker: {e}')
            self.is_running = False
            return False
        finally:
            self.stop()
    
    def stop(self):
        """Stop capture worker"""
        logger.info('Stopping capture worker...')
        self.should_stop = True
        self.is_running = False
        
        # Stop candump process
        if self.candump_process:
            try:
                # Check if process is still running
                if self.candump_process.poll() is None:
                    # Process is still running, terminate it
                    self.candump_process.terminate()
                    # Wait for graceful shutdown
                    try:
                        self.candump_process.wait(timeout=5)
                        logger.info('candump process terminated gracefully')
                    except subprocess.TimeoutExpired:
                        logger.warning('candump did not terminate gracefully, killing...')
                        self.candump_process.kill()
                        self.candump_process.wait()
                        logger.info('candump process killed')
                else:
                    logger.info(f'candump process already exited with code {self.candump_process.returncode}')
            except ProcessLookupError:
                logger.warning('candump process not found (may have already exited)')
            except Exception as e:
                logger.error(f'Error stopping candump process: {e}', exc_info=True)
            finally:
                self.candump_process = None
        
        # Final message count and metadata update
        try:
            if self.current_file and self.current_file.exists():
                self.message_count = self._count_messages_in_file(self.current_file)
            self._update_metadata()
        except Exception as e:
            logger.error(f'Error updating final metadata: {e}')
        
        logger.info(f'Capture worker stopped. Total messages: {self.message_count}')


def main():
    """Main entry point for capture worker process"""
    if len(sys.argv) < 2:
        print("Usage: capture_worker.py <session_config_json>")
        sys.exit(1)
    
    # Load session config from JSON
    config_json = sys.argv[1]
    session_config = json.loads(config_json)
    
    # Get directories from config or use defaults
    capture_dir = Path(session_config.get('capture_dir', './storage/captures'))
    metadata_dir = Path(session_config.get('metadata_dir', './storage/metadata'))
    
    # Create worker and run
    worker = CaptureWorker(session_config, capture_dir, metadata_dir)
    success = worker.start()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
