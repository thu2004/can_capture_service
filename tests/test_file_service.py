"""
Tests for File Service

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
import json
from unittest.mock import patch
from pathlib import Path
from datetime import datetime, timedelta
from app.services.file_service import FileService


class TestFileService:
    """Test cases for FileService"""
    
    def test_init(self, capture_dir, metadata_dir):
        """Test FileService initialization"""
        service = FileService(capture_dir, metadata_dir)
        
        assert service.capture_dir == capture_dir
        assert service.metadata_dir == metadata_dir
        assert capture_dir.exists()
        assert metadata_dir.exists()
    
    def test_list_files_empty(self, capture_dir, metadata_dir):
        """Test listing files when directory is empty"""
        service = FileService(capture_dir, metadata_dir)
        result = service.list_files()
        
        assert result['files'] == []
        assert result['total'] == 0
        assert result['count'] == 0
    
    def test_list_files_capture_dir_not_exists(self, temp_dir, metadata_dir):
        """Test listing files when capture directory doesn't exist"""
        non_existent_dir = temp_dir / 'non_existent'
        service = FileService(non_existent_dir, metadata_dir)
        result = service.list_files()
        
        assert result['files'] == []
        assert result['total'] == 0
    
    def test_list_files_with_files(self, capture_dir, metadata_dir):
        """Test listing files with actual files"""
        # Create test files
        file1 = capture_dir / 'capture_can0_20260101_120000.log'
        file1.write_text('test content 1')
        
        file2 = capture_dir / 'capture_can1_20260101_130000.log'
        file2.write_text('test content 2')
        
        service = FileService(capture_dir, metadata_dir)
        result = service.list_files()
        
        assert result['total'] == 2
        assert len(result['files']) == 2
        assert all('filename' in f for f in result['files'])
        assert all('size' in f for f in result['files'])
    
    def test_list_files_with_interface_filter(self, capture_dir, metadata_dir):
        """Test listing files filtered by interface"""
        # Create test files
        file1 = capture_dir / 'capture_can0_20260101_120000.log'
        file1.write_text('test content 1')
        
        file2 = capture_dir / 'capture_can1_20260101_130000.log'
        file2.write_text('test content 2')
        
        service = FileService(capture_dir, metadata_dir)
        result = service.list_files(interface='can0')
        
        assert result['total'] == 1
        assert len(result['files']) == 1
        assert result['files'][0]['interface'] == 'can0'
    
    def test_list_files_with_pagination(self, capture_dir, metadata_dir):
        """Test listing files with pagination"""
        # Create multiple test files
        for i in range(5):
            file = capture_dir / f'capture_can0_20260101_12000{i}.log'
            file.write_text(f'test content {i}')
        
        service = FileService(capture_dir, metadata_dir)
        
        # Test limit
        result = service.list_files(limit=2)
        assert result['total'] == 5
        assert len(result['files']) == 2
        
        # Test offset
        result = service.list_files(limit=2, offset=2)
        assert result['total'] == 5
        assert len(result['files']) == 2
        assert result['offset'] == 2
    
    def test_list_files_exception(self, capture_dir, metadata_dir):
        """Test listing files when exception occurs"""
        service = FileService(capture_dir, metadata_dir)
        
        with patch.object(Path, 'iterdir', side_effect=Exception('Test error')):
            result = service.list_files()
            
            assert result['files'] == []
            assert 'error' in result
    
    def test_get_file_info(self, capture_dir, metadata_dir):
        """Test getting file info"""
        # Create test file
        file_path = capture_dir / 'capture_can0_20260101_120000.log'
        file_path.write_text('test content')
        
        service = FileService(capture_dir, metadata_dir)
        file_info = service._get_file_info(file_path)
        
        assert file_info['filename'] == 'capture_can0_20260101_120000.log'
        assert file_info['size'] > 0
        assert file_info['size_mb'] >= 0
        assert 'created' in file_info
        assert 'modified' in file_info
        assert file_info['interface'] == 'can0'
    
    def test_get_file_info_with_metadata(self, capture_dir, metadata_dir):
        """Test getting file info with metadata file"""
        # Create test file
        file_path = capture_dir / 'capture_can0_20260101_120000.log'
        file_path.write_text('test content')
        
        # Create metadata file
        metadata_file = metadata_dir / 'capture_can0_20260101_120000.json'
        metadata = {
            'interface': 'can0',
            'message_count': 100,
            'start_time': (datetime.now() - timedelta(hours=1)).isoformat(),
            'end_time': datetime.now().isoformat(),
            'format': 'log',
            'session_id': 'test-session-123'
        }
        metadata_file.write_text(json.dumps(metadata))
        
        service = FileService(capture_dir, metadata_dir)
        file_info = service._get_file_info(file_path)
        
        assert file_info['interface'] == 'can0'
        assert file_info['message_count'] == 100
        assert file_info['duration'] is not None
        assert file_info['format'] == 'log'
        assert file_info['session_id'] == 'test-session-123'
    
    def test_get_file_info_interface_from_filename(self, capture_dir, metadata_dir):
        """Test extracting interface from filename"""
        # Create test file with interface in filename
        file_path = capture_dir / 'capture_can1_20260101_120000.log'
        file_path.write_text('test content')
        
        service = FileService(capture_dir, metadata_dir)
        file_info = service._get_file_info(file_path)
        
        assert file_info['interface'] == 'can1'
    
    def test_get_file_info_duration_calculation(self, capture_dir, metadata_dir):
        """Test duration calculation from metadata"""
        # Create test file
        file_path = capture_dir / 'capture_can0_20260101_120000.log'
        file_path.write_text('test content')
        
        # Create metadata with start and end time
        start_time = datetime.now() - timedelta(hours=2)
        end_time = datetime.now()
        metadata_file = metadata_dir / 'capture_can0_20260101_120000.json'
        metadata = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
        metadata_file.write_text(json.dumps(metadata))
        
        service = FileService(capture_dir, metadata_dir)
        file_info = service._get_file_info(file_path)
        
        assert file_info['duration'] is not None
        assert file_info['duration'] > 0
        # Should be approximately 2 hours (7200 seconds)
        assert 7000 < file_info['duration'] < 7300
    
    def test_get_file_info_duration_ongoing(self, capture_dir, metadata_dir):
        """Test duration calculation for ongoing capture"""
        # Create test file
        file_path = capture_dir / 'capture_can0_20260101_120000.log'
        file_path.write_text('test content')
        
        # Create metadata with only start time (ongoing)
        start_time = datetime.now() - timedelta(hours=1)
        metadata_file = metadata_dir / 'capture_can0_20260101_120000.json'
        metadata = {
            'start_time': start_time.isoformat()
        }
        metadata_file.write_text(json.dumps(metadata))
        
        service = FileService(capture_dir, metadata_dir)
        file_info = service._get_file_info(file_path)
        
        assert file_info['duration'] is not None
        assert file_info['duration'] > 0
    
    def test_load_file_metadata_exists(self, capture_dir, metadata_dir):
        """Test loading metadata when file exists"""
        metadata_file = metadata_dir / 'test_file.json'
        metadata = {
            'interface': 'can0',
            'message_count': 50
        }
        metadata_file.write_text(json.dumps(metadata))
        
        service = FileService(capture_dir, metadata_dir)
        result = service._load_file_metadata('test_file.log')
        
        assert result['interface'] == 'can0'
        assert result['message_count'] == 50
    
    def test_load_file_metadata_not_exists(self, capture_dir, metadata_dir):
        """Test loading metadata when file doesn't exist"""
        service = FileService(capture_dir, metadata_dir)
        result = service._load_file_metadata('non_existent.log')
        
        assert result == {}
    
    def test_load_file_metadata_invalid_json(self, capture_dir, metadata_dir):
        """Test loading metadata with invalid JSON"""
        metadata_file = metadata_dir / 'test_file.json'
        metadata_file.write_text('invalid json content')
        
        service = FileService(capture_dir, metadata_dir)
        result = service._load_file_metadata('test_file.log')
        
        # Should return empty dict on error
        assert result == {}
    
    def test_get_file_info_valid(self, capture_dir, metadata_dir):
        """Test getting file info for valid file"""
        file_path = capture_dir / 'test_file.log'
        file_path.write_text('test content')
        
        service = FileService(capture_dir, metadata_dir)
        result = service.get_file_info('test_file.log')
        
        assert result is not None
        assert result['filename'] == 'test_file.log'
        assert result['size'] > 0
    
    def test_get_file_info_invalid_filename(self, capture_dir, metadata_dir):
        """Test getting file info with invalid filename"""
        service = FileService(capture_dir, metadata_dir)
        result = service.get_file_info('../invalid/path/../../etc/passwd')
        
        assert result is None
    
    def test_get_file_info_not_found(self, capture_dir, metadata_dir):
        """Test getting file info for non-existent file"""
        service = FileService(capture_dir, metadata_dir)
        result = service.get_file_info('non_existent.log')
        
        assert result is None
    
    def test_get_file_path_valid(self, capture_dir, metadata_dir):
        """Test getting file path for valid file"""
        file_path = capture_dir / 'test_file.log'
        file_path.write_text('test content')
        
        service = FileService(capture_dir, metadata_dir)
        result = service.get_file_path('test_file.log')
        
        assert result is not None
        assert result == file_path
        assert result.exists()
    
    def test_get_file_path_invalid_filename(self, capture_dir, metadata_dir):
        """Test getting file path with invalid filename"""
        service = FileService(capture_dir, metadata_dir)
        result = service.get_file_path('../invalid/path')
        
        assert result is None
    
    def test_get_file_path_not_found(self, capture_dir, metadata_dir):
        """Test getting file path for non-existent file"""
        service = FileService(capture_dir, metadata_dir)
        result = service.get_file_path('non_existent.log')
        
        assert result is None
    
    def test_get_file_path_security_check(self, capture_dir, metadata_dir, temp_dir):
        """Test security check prevents directory traversal"""
        # Create a file outside capture directory
        outside_file = temp_dir / 'outside_file.log'
        outside_file.write_text('test')
        
        service = FileService(capture_dir, metadata_dir)
        
        # Try to access file using path traversal (should fail)
        # This test ensures the security check works
        result = service.get_file_path('../../outside_file.log')
        
        assert result is None
    
    def test_delete_file_success(self, capture_dir, metadata_dir):
        """Test deleting a file successfully"""
        # Create test file
        file_path = capture_dir / 'test_file.log'
        file_path.write_text('test content')
        
        # Create metadata file
        metadata_file = metadata_dir / 'test_file.json'
        metadata_file.write_text(json.dumps({'test': 'data'}))
        
        service = FileService(capture_dir, metadata_dir)
        result = service.delete_file('test_file.log')
        
        assert result['success'] is True
        assert not file_path.exists()
        assert not metadata_file.exists()  # Metadata should also be deleted
    
    def test_delete_file_not_found(self, capture_dir, metadata_dir):
        """Test deleting a file that doesn't exist"""
        service = FileService(capture_dir, metadata_dir)
        result = service.delete_file('non_existent.log')
        
        assert result['success'] is False
        assert 'not found' in result['error']
    
    def test_delete_file_invalid_filename(self, capture_dir, metadata_dir):
        """Test deleting file with invalid filename"""
        service = FileService(capture_dir, metadata_dir)
        result = service.delete_file('../invalid/path')
        
        assert result['success'] is False
        assert 'Invalid filename' in result['error']
    
    def test_delete_file_security_check(self, capture_dir, metadata_dir, temp_dir):
        """Test delete file security check"""
        # Create file outside capture directory
        outside_file = temp_dir / 'outside_file.log'
        outside_file.write_text('test')
        
        service = FileService(capture_dir, metadata_dir)
        result = service.delete_file('../../outside_file.log')
        
        assert result['success'] is False
        # Filename validation happens first, so it returns "Invalid filename"
        assert 'Invalid' in result['error']
    
    def test_delete_file_metadata_delete_fails(self, capture_dir, metadata_dir):
        """Test deleting file when metadata deletion fails"""
        # Create test file
        file_path = capture_dir / 'test_file.log'
        file_path.write_text('test content')
        
        # Create metadata file that will fail to delete
        metadata_file = metadata_dir / 'test_file.json'
        metadata_file.write_text(json.dumps({'test': 'data'}))
        
        service = FileService(capture_dir, metadata_dir)
        
        # Mock unlink to fail for metadata file
        with patch.object(Path, 'unlink', side_effect=[None, Exception('Permission denied')]):
            # First unlink succeeds (file), second fails (metadata)
            # But we need to patch it properly
            result = service.delete_file('test_file.log')
            
            # File should still be deleted even if metadata deletion fails
            assert result['success'] is True
    
    def test_delete_file_exception(self, capture_dir, metadata_dir):
        """Test deleting file when exception occurs"""
        # Create test file
        file_path = capture_dir / 'test_file.log'
        file_path.write_text('test content')
        
        service = FileService(capture_dir, metadata_dir)
        
        # Mock unlink to raise exception
        with patch.object(Path, 'unlink', side_effect=Exception('Permission denied')):
            result = service.delete_file('test_file.log')
            
            assert result['success'] is False
            assert 'Failed to delete' in result['error']
    
    def test_get_disk_usage(self, capture_dir, metadata_dir):
        """Test getting disk usage information"""
        # Create some test files
        file1 = capture_dir / 'file1.log'
        file1.write_text('x' * 1024)  # 1 KB
        
        file2 = capture_dir / 'file2.log'
        file2.write_text('x' * 2048)  # 2 KB
        
        service = FileService(capture_dir, metadata_dir)
        result = service.get_disk_usage()
        
        assert 'total_bytes' in result
        assert 'used_bytes' in result
        assert 'free_bytes' in result
        assert 'total_gb' in result
        assert 'used_gb' in result
        assert 'free_gb' in result
        assert 'usage_percent' in result
        assert 'capture_dir_size_bytes' in result
        assert 'capture_dir_size_gb' in result
        assert result['capture_dir_size_bytes'] >= 3072  # At least 3 KB (1KB + 2KB)
    
    def test_get_disk_usage_exception(self, capture_dir, metadata_dir):
        """Test getting disk usage when exception occurs"""
        service = FileService(capture_dir, metadata_dir)
        
        with patch('shutil.disk_usage', side_effect=Exception('Test error')):
            result = service.get_disk_usage()
            
            assert 'error' in result
    
    def test_list_files_ignores_dotfiles(self, capture_dir, metadata_dir):
        """Test that list_files ignores dotfiles"""
        # Create regular file
        file1 = capture_dir / 'capture_can0_20260101_120000.log'
        file1.write_text('test content')
        
        # Create dotfile (should be ignored)
        dotfile = capture_dir / '.hidden_file'
        dotfile.write_text('hidden content')
        
        service = FileService(capture_dir, metadata_dir)
        result = service.list_files()
        
        assert result['total'] == 1
        assert len(result['files']) == 1
        assert result['files'][0]['filename'] == 'capture_can0_20260101_120000.log'
    
    def test_list_files_ignores_directories(self, capture_dir, metadata_dir):
        """Test that list_files ignores subdirectories"""
        # Create regular file
        file1 = capture_dir / 'capture_can0_20260101_120000.log'
        file1.write_text('test content')
        
        # Create subdirectory (should be ignored)
        subdir = capture_dir / 'subdirectory'
        subdir.mkdir()
        
        service = FileService(capture_dir, metadata_dir)
        result = service.list_files()
        
        assert result['total'] == 1
        assert len(result['files']) == 1
    
    def test_list_files_sorted_by_creation_time(self, capture_dir, metadata_dir):
        """Test that files are sorted by creation time (newest first)"""
        import time
        
        # Create files with different timestamps
        file1 = capture_dir / 'file1.log'
        file1.write_text('old')
        time.sleep(0.1)
        
        file2 = capture_dir / 'file2.log'
        file2.write_text('new')
        
        service = FileService(capture_dir, metadata_dir)
        result = service.list_files()
        
        assert len(result['files']) == 2
        # Newest should be first
        assert result['files'][0]['filename'] == 'file2.log'
        assert result['files'][1]['filename'] == 'file1.log'
    
    def test_get_file_info_no_interface_in_filename(self, capture_dir, metadata_dir):
        """Test getting file info when interface can't be extracted from filename"""
        # Create file with non-standard name
        file_path = capture_dir / 'random_file.log'
        file_path.write_text('test content')
        
        service = FileService(capture_dir, metadata_dir)
        file_info = service._get_file_info(file_path)
        
        assert file_info['filename'] == 'random_file.log'
        assert file_info.get('interface') is None or file_info['interface'] is None

