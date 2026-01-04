"""
Tests for CAN Handler (candump integration)

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
from worker.can_handler import CANHandler


class TestCANHandler:
    """Test cases for CANHandler"""
    
    def test_init(self):
        """Test CANHandler initialization"""
        handler = CANHandler('can0', bitrate=500000)
        
        assert handler.interface == 'can0'
        assert handler.bitrate == 500000
        assert handler.process is None
        assert handler.is_running is False
    
    @patch('subprocess.run')
    def test_connect_success(self, mock_subprocess_run):
        """Test connecting to CAN bus successfully"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess_run.return_value = mock_result
        
        handler = CANHandler('can0')
        result = handler.connect()
        
        assert result is True
        assert handler.is_running is True
    
    @patch('subprocess.run')
    def test_connect_candump_not_found(self, mock_subprocess_run):
        """Test connecting when candump is not found"""
        mock_result = Mock()
        mock_result.returncode = 1  # candump not found
        mock_subprocess_run.return_value = mock_result
        
        handler = CANHandler('can0')
        result = handler.connect()
        
        assert result is False
        assert handler.is_running is False
    
    @patch('subprocess.Popen')
    def test_start_capture_success(self, mock_popen, temp_dir):
        """Test starting capture successfully"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        output_file = temp_dir / 'test_capture.log'
        
        handler = CANHandler('can0')
        handler.is_running = True
        
        with patch('builtins.open', mock_open()):
            result = handler.start_capture(str(output_file))
        
        assert result is True
        assert handler.process is not None
    
    @patch('subprocess.Popen')
    def test_start_capture_error(self, mock_popen):
        """Test starting capture with error"""
        mock_popen.side_effect = Exception('Failed to start candump')
        
        handler = CANHandler('can0')
        handler.is_running = True
        
        result = handler.start_capture('/tmp/test.log')
        
        assert result is False
        assert handler.is_running is False
    
    def test_is_alive_running(self, mock_candump_process):
        """Test checking if process is alive when running"""
        handler = CANHandler('can0')
        handler.process = mock_candump_process
        
        assert handler.is_alive() is True
    
    def test_is_alive_not_running(self):
        """Test checking if process is alive when not running"""
        handler = CANHandler('can0')
        handler.process = None
        
        assert handler.is_alive() is False
    
    def test_is_alive_process_exited(self):
        """Test checking if process is alive when process has exited"""
        mock_process = Mock()
        mock_process.poll.return_value = 1  # Process exited
        
        handler = CANHandler('can0')
        handler.process = mock_process
        
        assert handler.is_alive() is False
    
    def test_disconnect(self, mock_candump_process):
        """Test disconnecting from CAN bus"""
        handler = CANHandler('can0')
        handler.process = mock_candump_process
        
        handler.disconnect()
        
        assert handler.process is None
        assert handler.is_running is False
        mock_candump_process.terminate.assert_called_once()
    
    def test_disconnect_timeout(self):
        """Test disconnecting when process doesn't terminate"""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired('candump', 5)
        
        handler = CANHandler('can0')
        handler.process = mock_process
        
        handler.disconnect()
        
        mock_process.kill.assert_called_once()
        assert handler.process is None
    
    def test_context_manager(self):
        """Test CANHandler as context manager"""
        handler = CANHandler('can0')
        
        def mock_connect():
            handler.is_running = True
            return True
        
        with patch.object(handler, 'connect', side_effect=mock_connect):
            with patch.object(handler, 'disconnect'):
                with handler as h:
                    assert h is handler
                    assert handler.is_running is True
                
                handler.disconnect.assert_called_once()

