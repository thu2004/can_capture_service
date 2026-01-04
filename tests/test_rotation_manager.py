"""
Tests for Rotation Manager

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
import pytest
import time
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime, timedelta
from worker.rotation_manager import RotationManager


class TestRotationManager:
    """Test cases for RotationManager"""
    
    def test_init(self, capture_dir):
        """Test RotationManager initialization"""
        session_config = {
            'rotation': {
                'strategy': 'size',
                'max_file_size_mb': 10.0
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        
        assert manager.capture_dir == capture_dir
        assert manager.space_limit_mb == 100.0
        assert manager.current_size_mb == 0.0
        assert manager.current_file_index == 1
    
    def test_init_with_existing_rotation_data(self, capture_dir):
        """Test initialization with existing rotation data"""
        session_config = {
            'rotation': {
                'strategy': 'size',
                'current_file_index': 5,
                'rotated_files': [
                    {'filename': 'file1.log', 'size_mb': 10.0},
                    {'filename': 'file2.log', 'size_mb': 15.0}
                ]
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        
        assert manager.current_file_index == 5
        assert len(manager.rotated_files) == 2
    
    def test_check_rotation_needed_file_not_exists(self, capture_dir):
        """Test rotation check when file doesn't exist"""
        session_config = {
            'rotation': {'strategy': 'size'},
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        non_existent = capture_dir / 'non_existent.log'
        
        needs_rotation, reason = manager.check_rotation_needed(non_existent)
        
        assert needs_rotation is False
        assert reason == ""
    
    def test_check_rotation_needed_space_limit(self, capture_dir):
        """Test rotation check when space limit is reached"""
        session_config = {
            'rotation': {'strategy': 'size'},
            'space_limit_mb': 10.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        manager.current_size_mb = 9.0  # Already using 9 MB
        
        # Create file that would exceed limit
        file_path = capture_dir / 'test.log'
        file_path.write_text('x' * (2 * 1024 * 1024))  # 2 MB file
        
        needs_rotation, reason = manager.check_rotation_needed(file_path)
        
        assert needs_rotation is True
        assert reason == "space_limit_reached"
    
    def test_check_rotation_needed_size_strategy(self, capture_dir):
        """Test rotation check with size strategy"""
        session_config = {
            'rotation': {
                'strategy': 'size',
                'max_file_size_mb': 1.0
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        
        # Create file larger than max
        file_path = capture_dir / 'test.log'
        file_path.write_text('x' * (2 * 1024 * 1024))  # 2 MB file
        
        needs_rotation, reason = manager.check_rotation_needed(file_path)
        
        assert needs_rotation is True
        assert reason == "file_size_limit"
    
    def test_check_rotation_needed_size_strategy_no_rotation(self, capture_dir):
        """Test rotation check when file size is below limit"""
        session_config = {
            'rotation': {
                'strategy': 'size',
                'max_file_size_mb': 10.0
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        
        # Create small file
        file_path = capture_dir / 'test.log'
        file_path.write_text('x' * 100)  # Small file
        
        needs_rotation, reason = manager.check_rotation_needed(file_path)
        
        assert needs_rotation is False
    
    def test_check_rotation_needed_time_strategy(self, capture_dir):
        """Test rotation check with time strategy"""
        session_config = {
            'rotation': {
                'strategy': 'time',
                'max_file_duration_seconds': 1
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        
        # Create old file
        file_path = capture_dir / 'test.log'
        file_path.write_text('test')
        
        # Mock file modification time to be old
        old_time = time.time() - 2  # 2 seconds ago
        with patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value.st_size = 100
            mock_stat.return_value.st_mtime = old_time
            
            needs_rotation, reason = manager.check_rotation_needed(file_path)
            
            assert needs_rotation is True
            assert reason == "file_duration_limit"
    
    def test_check_rotation_needed_count_strategy(self, capture_dir):
        """Test rotation check with count strategy"""
        session_config = {
            'rotation': {
                'strategy': 'count',
                'max_files': 2
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        manager.rotated_files = [
            {'filename': 'file1.log', 'size_mb': 1.0}
        ]
        
        file_path = capture_dir / 'test.log'
        file_path.write_text('test')
        
        needs_rotation, reason = manager.check_rotation_needed(file_path)
        
        assert needs_rotation is True
        assert reason == "file_count_limit"
    
    def test_rotate_file_stop_action(self, capture_dir):
        """Test file rotation with stop action"""
        session_config = {
            'rotation': {
                'rotation_action': 'stop'
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        file_path = capture_dir / 'test.log'
        file_path.write_text('test')
        
        result = manager.rotate_file(file_path, 'test', 'log')
        
        assert result is None
    
    def test_rotate_file_success(self, capture_dir):
        """Test successful file rotation"""
        session_config = {
            'rotation': {
                'rotation_action': 'rotate'
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        file_path = capture_dir / 'test.log'
        file_path.write_text('test content')
        
        result = manager.rotate_file(file_path, 'test', 'log')
        
        assert result is not None
        assert result.exists()
        assert result.name == 'test_001.log'
        assert len(manager.rotated_files) == 1
    
    def test_rotate_file_increments_index(self, capture_dir):
        """Test that rotation increments file index"""
        session_config = {
            'rotation': {
                'rotation_action': 'rotate',
                'current_file_index': 3
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        file_path = capture_dir / 'test.log'
        file_path.write_text('test')
        
        result = manager.rotate_file(file_path, 'test', 'log')
        
        assert result.name == 'test_003.log'
        assert manager.current_file_index == 4  # Incremented after rotation
    
    def test_rotate_file_handles_existing_file(self, capture_dir):
        """Test rotation when target filename already exists"""
        session_config = {
            'rotation': {
                'rotation_action': 'rotate'
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        
        # Create existing rotated file
        existing = capture_dir / 'test_001.log'
        existing.write_text('existing')
        
        file_path = capture_dir / 'test.log'
        file_path.write_text('test')
        
        result = manager.rotate_file(file_path, 'test', 'log')
        
        # Should skip to next index
        assert result.name == 'test_002.log'
    
    def test_rotate_file_delete_oldest(self, capture_dir):
        """Test rotation with delete_oldest action"""
        session_config = {
            'rotation': {
                'rotation_action': 'delete_oldest',
                'max_files': 2
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        
        # Create rotated files
        old_file = capture_dir / 'test_001.log'
        old_file.write_text('old')
        manager.rotated_files = [
            {'filename': 'test_001.log', 'size_mb': 1.0}
        ]
        manager.current_size_mb = 1.0
        
        file_path = capture_dir / 'test.log'
        file_path.write_text('test')
        
        result = manager.rotate_file(file_path, 'test', 'log')
        
        assert result is not None
        assert not old_file.exists()  # Oldest file should be deleted
        assert len(manager.rotated_files) == 1  # Only new rotated file
    
    def test_rotate_file_exception(self, capture_dir):
        """Test rotation when exception occurs"""
        session_config = {
            'rotation': {
                'rotation_action': 'rotate'
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        file_path = capture_dir / 'test.log'
        file_path.write_text('test')
        
        with patch.object(Path, 'rename', side_effect=Exception('Permission denied')):
            result = manager.rotate_file(file_path, 'test', 'log')
            
            assert result is None
    
    def test_update_size_tracking(self, capture_dir):
        """Test updating size tracking"""
        session_config = {
            'rotation': {},
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        manager.rotated_files = [
            {'filename': 'file1.log', 'size_mb': 10.0},
            {'filename': 'file2.log', 'size_mb': 15.0}
        ]
        
        file_path = capture_dir / 'current.log'
        file_path.write_text('x' * (1024 * 1024))  # 1 MB
        
        manager.update_size_tracking(file_path)
        
        # Should be 10 + 15 + 1 = 26 MB
        assert manager.current_size_mb >= 25.0
        assert manager.current_size_mb <= 27.0
    
    def test_update_size_tracking_file_not_exists(self, capture_dir):
        """Test size tracking when file doesn't exist"""
        session_config = {
            'rotation': {},
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        manager.rotated_files = [
            {'filename': 'file1.log', 'size_mb': 10.0}
        ]
        
        non_existent = capture_dir / 'non_existent.log'
        manager.update_size_tracking(non_existent)
        
        # Should only count rotated files
        assert manager.current_size_mb == 10.0
    
    def test_get_space_remaining_mb(self, capture_dir):
        """Test getting remaining space"""
        session_config = {
            'rotation': {},
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        manager.current_size_mb = 30.0
        
        remaining = manager.get_space_remaining_mb()
        
        assert remaining == 70.0
    
    def test_get_space_remaining_mb_zero(self, capture_dir):
        """Test getting remaining space when limit is reached"""
        session_config = {
            'rotation': {},
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        manager.current_size_mb = 150.0  # Exceeds limit
        
        remaining = manager.get_space_remaining_mb()
        
        assert remaining == 0.0
    
    def test_get_rotation_info(self, capture_dir):
        """Test getting rotation information"""
        session_config = {
            'rotation': {
                'last_rotation_time': datetime.now().isoformat()
            },
            'space_limit_mb': 100.0
        }
        
        manager = RotationManager(session_config, capture_dir)
        manager.current_file_index = 5
        manager.current_size_mb = 25.0
        manager.rotated_files = [
            {'filename': 'file1.log', 'size_mb': 10.0},
            {'filename': 'file2.log', 'size_mb': 15.0}
        ]
        
        info = manager.get_rotation_info()
        
        assert info['current_file_index'] == 5
        assert info['total_files'] == 3  # 2 rotated + 1 current
        assert info['current_size_mb'] == 25.0
        assert info['space_limit_mb'] == 100.0
        assert info['space_remaining_mb'] == 75.0
        assert info['rotated_files_count'] == 2
        assert 'last_rotation_time' in info

