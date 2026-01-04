"""
Tests for Capture Worker

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
import pytest
import signal
import subprocess
import json
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
from datetime import datetime
from worker.capture_worker import CaptureWorker


class TestCaptureWorker:
    """Test cases for CaptureWorker"""
    
    def test_init(self, session_config, capture_dir, metadata_dir):
        """Test CaptureWorker initialization"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        assert worker.session_id == session_config['session_id']
        assert worker.interface == session_config['interface']
        assert worker.bitrate == session_config.get('bitrate')
        assert worker.output_file == session_config['output_file']
        assert worker.capture_dir == capture_dir
        assert worker.metadata_dir == metadata_dir
        assert worker.is_running is False
        assert worker.should_stop is False
        assert worker.message_count == 0
    
    def test_signal_handler(self, session_config, capture_dir, metadata_dir):
        """Test signal handler"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        assert worker.should_stop is False
        worker._signal_handler(signal.SIGTERM, None)
        assert worker.should_stop is True
    
    def test_count_messages_in_file(self, session_config, capture_dir, metadata_dir):
        """Test counting messages in file"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        # Create test file with messages
        file_path = capture_dir / 'test.log'
        file_path.write_text('(000.000000) can0 123#DEADBEEF\n' * 10)
        
        count = worker._count_messages_in_file(file_path)
        
        assert count == 10
    
    def test_count_messages_in_file_not_exists(self, session_config, capture_dir, metadata_dir):
        """Test counting messages when file doesn't exist"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        non_existent = capture_dir / 'non_existent.log'
        count = worker._count_messages_in_file(non_existent)
        
        assert count == 0
    
    def test_count_messages_in_file_exception(self, session_config, capture_dir, metadata_dir):
        """Test counting messages when exception occurs"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        file_path = capture_dir / 'test.log'
        
        with patch('builtins.open', side_effect=IOError('Permission denied')):
            count = worker._count_messages_in_file(file_path)
            
            assert count == 0
    
    @patch('subprocess.run')
    def test_start_candump_not_found(self, mock_subprocess_run, session_config, capture_dir, metadata_dir):
        """Test starting when candump is not found"""
        mock_result = Mock()
        mock_result.returncode = 1  # candump not found
        mock_subprocess_run.return_value = mock_result
        
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        result = worker.start()
        
        assert result is False
        assert worker.is_running is False
    
    @patch('subprocess.Popen')
    @patch('subprocess.run')
    def test_start_candump_exits_immediately(self, mock_subprocess_run, mock_popen, session_config, capture_dir, metadata_dir):
        """Test starting when candump exits immediately"""
        # Mock candump check succeeds
        mock_check = Mock()
        mock_check.returncode = 0
        mock_subprocess_run.return_value = mock_check
        
        # Mock candump process that exits immediately
        mock_process = Mock()
        mock_process.poll.return_value = 1  # Process exited
        mock_process.stderr = Mock()
        mock_process.stderr.read.return_value = 'Error: Interface not found'
        mock_popen.return_value = mock_process
        
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        with patch('time.sleep'):
            result = worker.start()
        
        assert result is False
    
    @patch('subprocess.Popen')
    @patch('subprocess.run')
    def test_start_success(self, mock_subprocess_run, mock_popen, session_config, capture_dir, metadata_dir):
        """Test successful start"""
        # Mock candump check
        mock_check = Mock()
        mock_check.returncode = 0
        mock_subprocess_run.return_value = mock_check
        
        # Mock candump process running
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.stderr = Mock()
        mock_popen.return_value = mock_process
        
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        # Make the loop exit after first iteration by setting should_stop in sleep
        call_count = [0]
        def sleep_side_effect(seconds):
            call_count[0] += 1
            # After the first sleep in the loop (which happens after the initial 0.2s sleep),
            # set should_stop to True to exit the loop
            if call_count[0] > 1:  # Skip the initial 0.2s sleep, exit after first loop sleep
                worker.should_stop = True
        
        with patch('time.sleep', side_effect=sleep_side_effect):
            with patch.object(worker, 'stop'):
                result = worker.start()
        
        # Should return True (started successfully, then stopped)
        assert result is True
    
    @patch('subprocess.Popen')
    @patch('subprocess.run')
    def test_start_candump_process_exits(self, mock_subprocess_run, mock_popen, session_config, capture_dir, metadata_dir):
        """Test when candump process exits unexpectedly"""
        # Mock candump check
        mock_check = Mock()
        mock_check.returncode = 0
        mock_subprocess_run.return_value = mock_check
        
        # Mock candump process that exits
        mock_process = Mock()
        mock_process.poll.side_effect = [None, 1]  # First check: running, second: exited
        mock_process.returncode = 1
        mock_process.stderr = Mock()
        mock_process.stderr.read.return_value = 'Error message'
        mock_popen.return_value = mock_process
        
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        with patch('time.sleep'):
            with patch.object(worker, 'stop'):
                with patch.object(worker, '_update_metadata'):
                    result = worker.start()
        
        assert worker.is_running is False
        assert worker.should_stop is True
    
    def test_check_and_rotate_no_rotation_needed(self, session_config, capture_dir, metadata_dir):
        """Test rotation check when rotation is not needed"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('test')
        
        # Mock rotation manager
        mock_rotation = Mock()
        mock_rotation.check_rotation_needed.return_value = (False, "")
        worker.rotation_manager = mock_rotation
        
        worker._check_and_rotate()
        
        # Should not rotate
        assert worker.current_file.name == 'test.log'
    
    @patch('subprocess.Popen')
    def test_check_and_rotate_needed(self, mock_popen, session_config, capture_dir, metadata_dir):
        """Test rotation when rotation is needed"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('test')
        
        # Mock candump process
        mock_process = Mock()
        mock_process.poll.return_value = None
        worker.candump_process = mock_process
        
        # Mock rotation manager
        mock_rotation = Mock()
        mock_rotation.check_rotation_needed.return_value = (True, "file_size_limit")
        new_file = capture_dir / 'test_001.log'
        new_file.touch()
        mock_rotation.rotate_file.return_value = new_file
        worker.rotation_manager = mock_rotation
        
        # Mock new candump process
        new_mock_process = Mock()
        new_mock_process.poll.return_value = None
        mock_popen.return_value = new_mock_process
        
        worker._check_and_rotate()
        
        # Should have rotated
        assert worker.current_file == new_file
        mock_process.terminate.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_check_and_rotate_stop_action(self, mock_popen, session_config, capture_dir, metadata_dir):
        """Test rotation when rotation action is stop"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('test')
        
        # Mock rotation manager that returns None (stop action)
        mock_rotation = Mock()
        mock_rotation.check_rotation_needed.return_value = (True, "file_size_limit")
        mock_rotation.rotate_file.return_value = None  # Stop action
        worker.rotation_manager = mock_rotation
        
        worker._check_and_rotate()
        
        # Should stop
        assert worker.should_stop is True
    
    def test_update_metadata(self, session_config, capture_dir, metadata_dir):
        """Test updating metadata file"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        worker.current_file = capture_dir / 'test.log'
        worker.message_count = 100
        worker.is_running = True
        
        # Mock rotation manager
        mock_rotation = Mock()
        mock_rotation.get_rotation_info.return_value = {'current_size_mb': 10.0}
        worker.rotation_manager = mock_rotation
        
        worker._update_metadata()
        
        metadata_file = metadata_dir / f"{session_config['session_id']}.json"
        assert metadata_file.exists()
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        assert metadata['session_id'] == session_config['session_id']
        assert metadata['interface'] == session_config['interface']
        assert metadata['status'] == 'running'
        assert metadata['message_count'] == 100
    
    def test_update_metadata_exception(self, session_config, capture_dir, metadata_dir):
        """Test metadata update when exception occurs"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        with patch('builtins.open', side_effect=IOError('Permission denied')):
            # Should not raise exception
            worker._update_metadata()
    
    def test_stop_no_process(self, session_config, capture_dir, metadata_dir):
        """Test stopping when no process is running"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        worker.candump_process = None
        
        worker.stop()
        
        assert worker.is_running is False
        assert worker.should_stop is True
    
    @patch('subprocess.Popen')
    def test_stop_process_terminates_gracefully(self, mock_popen, session_config, capture_dir, metadata_dir):
        """Test stopping when process terminates gracefully"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        mock_process = Mock()
        mock_process.poll.side_effect = [None, 0]  # Running, then terminated
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        worker.candump_process = mock_process
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('test')
        
        worker.stop()
        
        mock_process.terminate.assert_called_once()
        assert worker.candump_process is None
    
    @patch('subprocess.Popen')
    def test_stop_process_needs_kill(self, mock_popen, session_config, capture_dir, metadata_dir):
        """Test stopping when process needs to be killed"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        mock_process = Mock()
        mock_process.poll.side_effect = [None, None]  # Still running
        mock_process.wait.side_effect = [subprocess.TimeoutExpired('candump', 5), None]
        worker.candump_process = mock_process
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('test')
        
        worker.stop()
        
        mock_process.kill.assert_called_once()
        assert worker.candump_process is None
    
    @patch('subprocess.Popen')
    def test_stop_process_already_exited(self, mock_popen, session_config, capture_dir, metadata_dir):
        """Test stopping when process already exited"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        mock_process = Mock()
        mock_process.poll.return_value = 1  # Already exited
        mock_process.returncode = 1
        worker.candump_process = mock_process
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('test')
        
        worker.stop()
        
        # Should not call terminate or kill
        assert not hasattr(mock_process.terminate, 'call_count') or mock_process.terminate.call_count == 0
        assert worker.candump_process is None
    
    @patch('subprocess.Popen')
    def test_stop_process_not_found(self, mock_popen, session_config, capture_dir, metadata_dir):
        """Test stopping when process is not found"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        mock_process = Mock()
        mock_process.poll.side_effect = ProcessLookupError()
        worker.candump_process = mock_process
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('test')
        
        worker.stop()
        
        assert worker.candump_process is None
    
    @patch('subprocess.Popen')
    def test_stop_exception(self, mock_popen, session_config, capture_dir, metadata_dir):
        """Test stopping when exception occurs"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        
        mock_process = Mock()
        mock_process.poll.side_effect = Exception('Unexpected error')
        worker.candump_process = mock_process
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('test')
        
        # Should not raise exception
        worker.stop()
        
        assert worker.candump_process is None
    
    def test_stop_updates_final_metadata(self, session_config, capture_dir, metadata_dir):
        """Test that stop updates final metadata"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('(000.000000) can0 123#DEADBEEF\n' * 5)
        worker.candump_process = None
        
        worker.stop()
        
        metadata_file = metadata_dir / f"{session_config['session_id']}.json"
        assert metadata_file.exists()
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        assert metadata['message_count'] == 5
        assert metadata['status'] == 'stopped'
    
    def test_stop_metadata_update_exception(self, session_config, capture_dir, metadata_dir):
        """Test stop when metadata update fails"""
        worker = CaptureWorker(session_config, capture_dir, metadata_dir)
        worker.current_file = capture_dir / 'test.log'
        worker.current_file.write_text('test')
        worker.candump_process = None
        
        with patch.object(worker, '_update_metadata', side_effect=Exception('Error')):
            # Should not raise exception
            worker.stop()

