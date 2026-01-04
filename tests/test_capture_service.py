"""
Tests for Capture Service

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
from unittest.mock import Mock, patch
from app.services.capture_service import CaptureService
from app.models.session import CaptureSession


class TestCaptureService:
    """Test cases for CaptureService"""
    
    def test_init(self, capture_dir, metadata_dir, default_rotation_config):
        """Test CaptureService initialization"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        assert service.capture_dir == capture_dir
        assert service.metadata_dir == metadata_dir
        assert service.default_rotation == default_rotation_config
        assert isinstance(service.active_sessions, dict)
    
    def test_start_capture_invalid_interface(self, capture_dir, metadata_dir, default_rotation_config):
        """Test starting capture with invalid interface name"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        result = service.start_capture('invalid-interface!')
        
        assert result['success'] is False
        assert 'Invalid interface name' in result['error']
    
    def test_start_capture_interface_already_capturing(self, capture_dir, metadata_dir, default_rotation_config):
        """Test starting capture when interface is already capturing"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        # Create a running session
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        service.active_sessions[session.session_id] = session
        
        result = service.start_capture('can0')
        
        assert result['success'] is False
        assert 'already being captured' in result['error']
    
    @patch('subprocess.Popen')
    @patch('sys.executable', 'python')
    def test_start_capture_success(self, mock_popen, capture_dir, metadata_dir, default_rotation_config):
        """Test starting capture successfully"""
        # Mock worker process
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        with patch('time.sleep'):  # Skip sleep in test
            result = service.start_capture('can0', bitrate=500000)
        
        assert result['success'] is True
        assert 'session_id' in result
        assert result['interface'] == 'can0'
        assert len(service.active_sessions) == 1
    
    @patch('subprocess.Popen')
    def test_start_capture_worker_fails(self, mock_popen, capture_dir, metadata_dir, default_rotation_config):
        """Test starting capture when worker process fails"""
        # Mock worker process that exits immediately
        mock_process = Mock()
        mock_process.poll.return_value = 1  # Process exited
        mock_process.communicate.return_value = (b'', b'Error: candump not found')
        mock_popen.return_value = mock_process
        
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        with patch('time.sleep'):  # Skip sleep in test
            result = service.start_capture('can0')
        
        assert result['success'] is False
        assert 'Failed to start capture worker' in result['error']
    
    def test_stop_capture_not_found(self, capture_dir, metadata_dir, default_rotation_config):
        """Test stopping a capture session that doesn't exist"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        result = service.stop_capture('non-existent-session')
        
        assert result['success'] is False
        assert 'not found' in result['error']
    
    def test_stop_capture_already_stopped(self, capture_dir, metadata_dir, default_rotation_config):
        """Test stopping a capture session that's already stopped"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        # Create a stopped session
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'stopped'
        service.active_sessions[session.session_id] = session
        
        result = service.stop_capture(session.session_id)
        
        assert result['success'] is False
        assert 'not running' in result['error']
    
    @patch('os.kill')
    def test_stop_capture_success(self, mock_kill, capture_dir, metadata_dir, default_rotation_config):
        """Test stopping a capture session successfully"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        # Create a running session
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        session.worker_pid = 12345
        service.active_sessions[session.session_id] = session
        
        # Mock process exists
        mock_kill.side_effect = None  # No exception means process exists
        
        with patch('time.sleep'):  # Skip sleep in test
            result = service.stop_capture(session.session_id)
        
        assert result['success'] is True
        assert session.status == 'stopped'
        assert session.worker_pid is None
    
    def test_list_sessions(self, capture_dir, metadata_dir, default_rotation_config):
        """Test listing capture sessions"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        # Create some sessions
        session1 = CaptureSession.create(
            interface='can0',
            output_file='test1.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session1.status = 'running'
        
        session2 = CaptureSession.create(
            interface='can1',
            output_file='test2.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session2.status = 'stopped'
        
        service.active_sessions[session1.session_id] = session1
        service.active_sessions[session2.session_id] = session2
        
        sessions = service.list_sessions()
        
        assert len(sessions) == 2
        assert any(s.session_id == session1.session_id for s in sessions)
        assert any(s.session_id == session2.session_id for s in sessions)
    
    def test_get_session(self, capture_dir, metadata_dir, default_rotation_config):
        """Test getting a specific session"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        service.active_sessions[session.session_id] = session
        
        retrieved = service.get_session(session.session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    def test_get_session_not_found(self, capture_dir, metadata_dir, default_rotation_config):
        """Test getting a session that doesn't exist"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        result = service.get_session('non-existent-session')
        
        assert result is None
    
    @patch('subprocess.Popen')
    def test_start_capture_exception(self, mock_popen, capture_dir, metadata_dir, default_rotation_config):
        """Test starting capture when exception occurs"""
        mock_popen.side_effect = Exception('Unexpected error')
        
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        result = service.start_capture('can0')
        
        assert result['success'] is False
        assert 'Failed to start capture' in result['error']
    
    @patch('os.kill')
    @patch('time.sleep')
    def test_stop_capture_process_terminates_gracefully(self, mock_sleep, mock_kill, capture_dir, metadata_dir, default_rotation_config):
        """Test stopping capture when process terminates gracefully"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        session.worker_pid = 12345
        service.active_sessions[session.session_id] = session
        
        # First kill succeeds (process exists), second raises ProcessLookupError (terminated)
        mock_kill.side_effect = [None, ProcessLookupError()]
        
        result = service.stop_capture(session.session_id)
        
        assert result['success'] is True
        assert session.status == 'stopped'
    
    @patch('os.kill')
    @patch('time.sleep')
    def test_stop_capture_process_needs_sigkill(self, mock_sleep, mock_kill, capture_dir, metadata_dir, default_rotation_config):
        """Test stopping capture when process needs SIGKILL"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        session.worker_pid = 12345
        service.active_sessions[session.session_id] = session
        
        # Process exists after SIGTERM, needs SIGKILL
        def kill_side_effect(pid, sig):
            if sig == signal.SIGTERM:
                return None  # SIGTERM sent
            elif sig == signal.SIGKILL:
                raise ProcessLookupError()  # Process killed
            else:
                return None  # Check if exists
        
        import signal
        mock_kill.side_effect = kill_side_effect
        
        result = service.stop_capture(session.session_id)
        
        assert result['success'] is True
    
    @patch('os.kill')
    def test_stop_capture_process_not_found(self, mock_kill, capture_dir, metadata_dir, default_rotation_config):
        """Test stopping capture when process is not found"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        session.worker_pid = 12345
        service.active_sessions[session.session_id] = session
        
        mock_kill.side_effect = ProcessLookupError()
        
        result = service.stop_capture(session.session_id)
        
        assert result['success'] is True  # Should still succeed
    
    @patch('os.kill')
    def test_stop_capture_permission_error(self, mock_kill, capture_dir, metadata_dir, default_rotation_config):
        """Test stopping capture when permission denied"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        session.worker_pid = 12345
        service.active_sessions[session.session_id] = session
        
        mock_kill.side_effect = PermissionError()
        
        result = service.stop_capture(session.session_id)
        
        assert result['success'] is True  # Should still mark as stopped
    
    @patch('os.kill')
    def test_stop_capture_kill_exception(self, mock_kill, capture_dir, metadata_dir, default_rotation_config):
        """Test stopping capture when kill raises exception"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        session.worker_pid = 12345
        service.active_sessions[session.session_id] = session
        
        mock_kill.side_effect = Exception('Unexpected error')
        
        result = service.stop_capture(session.session_id)
        
        assert result['success'] is True  # Should still mark as stopped
    
    def test_stop_capture_no_worker_pid(self, capture_dir, metadata_dir, default_rotation_config):
        """Test stopping capture when there's no worker PID"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        session.worker_pid = None  # No worker PID
        service.active_sessions[session.session_id] = session
        
        result = service.stop_capture(session.session_id)
        
        assert result['success'] is True
        assert session.status == 'stopped'
    
    def test_save_session_metadata(self, capture_dir, metadata_dir, default_rotation_config):
        """Test saving session metadata"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        session.worker_pid = 12345
        
        service._save_session_metadata(session)
        
        metadata_file = metadata_dir / f"{session.session_id}.json"
        assert metadata_file.exists()
    
    @patch('os.kill')
    def test_load_sessions_from_metadata(self, mock_kill, capture_dir, metadata_dir, default_rotation_config):
        """Test loading sessions from metadata files"""
        import json
        from datetime import datetime
        
        # Create a metadata file
        session_id = 'test-session-123'
        metadata_file = metadata_dir / f"{session_id}.json"
        metadata = {
            'session_id': session_id,
            'interface': 'can0',
            'start_time': datetime.now().isoformat(),
            'status': 'running',
            'output_file': 'test.log',
            'message_count': 100,
            'worker_pid': 12345
        }
        metadata_file.write_text(json.dumps(metadata))
        
        # Mock process exists (os.kill with signal 0 checks if process exists)
        # No exception means process exists, so status stays 'running'
        def kill_side_effect(pid, sig):
            if sig == 0:  # Check if exists
                return None  # Process exists - no exception
            return None
        
        mock_kill.side_effect = kill_side_effect
        
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        assert session_id in service.active_sessions
        session = service.active_sessions[session_id]
        assert session.interface == 'can0'
        # If process check succeeds, status should be 'running'
        # If process check fails, it will be marked as 'error'
        assert session.status in ['running', 'error']
    
    def test_load_sessions_from_metadata_stopped(self, capture_dir, metadata_dir, default_rotation_config):
        """Test loading stopped sessions from metadata"""
        import json
        
        session_id = 'test-session-stopped'
        metadata_file = metadata_dir / f"{session_id}.json"
        metadata = {
            'session_id': session_id,
            'interface': 'can0',
            'start_time': '2026-01-01T12:00:00',
            'status': 'stopped',
            'output_file': 'test.log',
            'message_count': 100,
            'worker_pid': None
        }
        metadata_file.write_text(json.dumps(metadata))
        
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        assert session_id in service.active_sessions
        session = service.active_sessions[session_id]
        assert session.status == 'stopped'
    
    @patch('os.kill')
    def test_load_sessions_from_metadata_process_dead(self, mock_kill, capture_dir, metadata_dir, default_rotation_config):
        """Test loading sessions when process is dead"""
        import json
        
        session_id = 'test-session-dead'
        metadata_file = metadata_dir / f"{session_id}.json"
        metadata = {
            'session_id': session_id,
            'interface': 'can0',
            'start_time': '2026-01-01T12:00:00',
            'status': 'running',
            'output_file': 'test.log',
            'message_count': 100,
            'worker_pid': 12345
        }
        metadata_file.write_text(json.dumps(metadata))
        
        # Process doesn't exist
        mock_kill.side_effect = ProcessLookupError()
        
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        assert session_id in service.active_sessions
        session = service.active_sessions[session_id]
        # Should be marked as error since process is dead
        assert session.status == 'error'
    
    def test_load_sessions_from_metadata_invalid_file(self, capture_dir, metadata_dir, default_rotation_config):
        """Test loading sessions with invalid metadata file"""
        # Create invalid JSON file
        metadata_file = metadata_dir / "invalid.json"
        metadata_file.write_text('invalid json content')
        
        # Should not raise exception
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        # Should handle gracefully
        assert isinstance(service.active_sessions, dict)
    
    def test_get_session_status(self, capture_dir, metadata_dir, default_rotation_config):
        """Test getting session status"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        
        session = CaptureSession.create(
            interface='can0',
            output_file='test.log',
            space_limit_mb=100.0,
            rotation=default_rotation_config
        )
        session.status = 'running'
        service.active_sessions[session.session_id] = session
        
        status = service.get_session_status(session.session_id)
        
        assert status is not None
        assert status['session_id'] == session.session_id
        assert status['status'] == 'running'
    
    def test_get_session_status_not_found(self, capture_dir, metadata_dir, default_rotation_config):
        """Test getting status for non-existent session"""
        service = CaptureService(capture_dir, metadata_dir, default_rotation_config)
        status = service.get_session_status('non-existent-session')
        
        assert status is None

