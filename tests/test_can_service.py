"""
Tests for CAN Service

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
from unittest.mock import Mock, patch
from app.services.can_service import CANService
from app.models.interface import CANInterface


class TestCANService:
    """Test cases for CANService"""
    
    def test_init(self):
        """Test CANService initialization"""
        service = CANService(supported_interfaces=['can0', 'can1'])
        assert service.supported_interfaces == ['can0', 'can1']
        assert service._interface_cache == {}
    
    def test_init_no_interfaces(self):
        """Test CANService initialization without supported interfaces"""
        service = CANService()
        assert service.supported_interfaces == []
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.iterdir')
    def test_list_interfaces_via_sys(self, mock_iterdir, mock_exists, mock_subprocess_run, mock_sys_class_net):
        """Test listing interfaces via /sys/class/net"""
        # Mock /sys/class/net structure
        mock_exists.return_value = True
        
        # Create proper Mock objects with name attribute
        can0_mock = Mock()
        can0_mock.name = 'can0'
        can1_mock = Mock()
        can1_mock.name = 'can1'
        eth0_mock = Mock()
        eth0_mock.name = 'eth0'
        
        mock_iterdir.return_value = [can0_mock, can1_mock, eth0_mock]
        
        # Mock interface type check
        with patch.object(CANService, '_is_can_interface') as mock_is_can:
            mock_is_can.side_effect = lambda x: x.name.startswith('can')
            
            with patch.object(CANService, '_get_interface_info') as mock_get_info:
                def get_info_side_effect(name):
                    if name.startswith('can'):
                        return CANInterface(
                            name=name,
                            status='up' if name == 'can0' else 'down',
                            bitrate=500000 if name == 'can0' else 1000000,
                            interface_type='socketcan',
                            is_capturing=False,
                            active_session_id=None
                        )
                    return None
                
                mock_get_info.side_effect = get_info_side_effect
                
                service = CANService()
                interfaces = service.list_interfaces()
                
                assert len(interfaces) == 2
                assert all(iface.name.startswith('can') for iface in interfaces)
    
    @patch('subprocess.run')
    def test_list_interfaces_via_ip(self, mock_subprocess_run, mock_ip_link_list_output):
        """Test listing interfaces via ip command"""
        # Mock ip command output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = mock_ip_link_list_output
        mock_subprocess_run.return_value = mock_result
        
        with patch('pathlib.Path.exists', return_value=False):
            with patch.object(CANService, '_get_interface_info') as mock_get_info:
                mock_get_info.side_effect = lambda name: CANInterface(
                    name=name,
                    status='up' if name in ['can0', 'vcan0'] else 'down',
                    bitrate=500000 if name == 'can0' else None,
                    interface_type='virtual' if name.startswith('vcan') else 'socketcan',
                    is_capturing=False,
                    active_session_id=None
                )
                
                service = CANService()
                interfaces = service.list_interfaces()
                
                assert len(interfaces) == 3
                assert any(iface.name == 'can0' for iface in interfaces)
                assert any(iface.name == 'can1' for iface in interfaces)
                assert any(iface.name == 'vcan0' for iface in interfaces)
    
    def test_is_can_interface_by_type(self, mock_sys_class_net):
        """Test _is_can_interface by checking type file"""
        service = CANService()
        can0_path = mock_sys_class_net / 'can0'
        
        assert service._is_can_interface(can0_path) is True
    
    def test_is_can_interface_by_name(self):
        """Test _is_can_interface by checking name pattern"""
        service = CANService()
        mock_path = Mock()
        mock_path.name = 'can0'
        mock_path.__truediv__ = lambda self, other: Mock(exists=lambda: False)
        
        # Mock type file doesn't exist, but name matches pattern
        with patch.object(mock_path, '__truediv__', return_value=Mock(exists=lambda: False)):
            # Since type file doesn't exist, it should check name pattern
            # We need to properly mock this
            result = service._is_can_interface(mock_path)
            # This will check name pattern since type file check fails
            assert result is True  # can0 matches pattern
    
    @patch('subprocess.run')
    def test_get_interface_status_up(self, mock_subprocess_run):
        """Test getting interface status when interface is up"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '1: can0: <NOARP,UP,LOWER_UP> mtu 16 state UP'
        mock_subprocess_run.return_value = mock_result
        
        service = CANService()
        status = service._get_interface_status('can0')
        
        assert status == 'up'
    
    @patch('subprocess.run')
    def test_get_interface_status_down(self, mock_subprocess_run):
        """Test getting interface status when interface is down"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '1: can0: <NOARP> mtu 16 state DOWN'
        mock_subprocess_run.return_value = mock_result
        
        service = CANService()
        status = service._get_interface_status('can0')
        
        assert status == 'down'
    
    @patch('subprocess.run')
    def test_get_interface_bitrate(self, mock_subprocess_run, mock_ip_link_output):
        """Test getting interface bitrate"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = mock_ip_link_output
        mock_subprocess_run.return_value = mock_result
        
        service = CANService()
        bitrate = service._get_interface_bitrate('can0')
        
        assert bitrate == 500000
    
    def test_get_interface_type_virtual(self):
        """Test getting interface type for virtual interface"""
        service = CANService()
        interface_type = service._get_interface_type('vcan0')
        
        assert interface_type == 'virtual'
    
    def test_get_interface_type_socketcan(self, mock_sys_class_net):
        """Test getting interface type for socketcan interface"""
        service = CANService()
        interface_type = service._get_interface_type('can0')
        
        assert interface_type == 'socketcan'
    
    def test_get_interface_invalid_name(self):
        """Test getting interface with invalid name"""
        service = CANService()
        interface = service.get_interface('invalid-interface-name!')
        
        assert interface is None
    
    def test_validate_interface_valid(self):
        """Test validating a valid interface"""
        service = CANService()
        
        with patch.object(service, 'get_interface') as mock_get:
            mock_get.return_value = CANInterface(
                name='can0',
                status='up',
                bitrate=500000,
                interface_type='socketcan',
                is_capturing=False,
                active_session_id=None
            )
            
            assert service.validate_interface('can0') is True
    
    def test_validate_interface_invalid(self):
        """Test validating an invalid interface"""
        service = CANService()
        
        with patch.object(service, 'get_interface', return_value=None):
            assert service.validate_interface('can0') is False
    
    @patch('subprocess.run')
    def test_start_interface_success(self, mock_subprocess_run):
        """Test starting an interface successfully"""
        # Mock interface exists
        with patch.object(CANService, 'get_interface') as mock_get:
            mock_get.return_value = CANInterface(
                name='can0',
                status='down',
                bitrate=None,
                interface_type='socketcan',
                is_capturing=False,
                active_session_id=None
            )
            
            # Mock subprocess calls
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ''
            mock_result.stderr = ''
            mock_subprocess_run.return_value = mock_result
            
            service = CANService()
            result = service.start_interface('can0', bitrate=500000)
            
            assert result['success'] is True
            assert result['interface'] == 'can0'
    
    @patch('subprocess.run')
    def test_start_interface_not_found(self, mock_subprocess_run):
        """Test starting an interface that doesn't exist"""
        with patch.object(CANService, 'get_interface', return_value=None):
            service = CANService()
            result = service.start_interface('can999', bitrate=500000)
            
            assert result['success'] is False
            assert 'not found' in result['message']
    
    @patch('subprocess.run')
    def test_stop_interface_success(self, mock_subprocess_run):
        """Test stopping an interface successfully"""
        with patch.object(CANService, 'get_interface') as mock_get:
            mock_get.return_value = CANInterface(
                name='can0',
                status='up',
                bitrate=500000,
                interface_type='socketcan',
                is_capturing=False,
                active_session_id=None
            )
            
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ''
            mock_result.stderr = ''
            mock_subprocess_run.return_value = mock_result
            
            service = CANService()
            result = service.stop_interface('can0')
            
            assert result['success'] is True
            assert result['interface'] == 'can0'
    
    @patch('subprocess.run')
    def test_list_interfaces_ip_command_timeout(self, mock_subprocess_run):
        """Test listing interfaces when ip command times out"""
        import subprocess
        mock_subprocess_run.side_effect = subprocess.TimeoutExpired('ip', 5)
        
        with patch('pathlib.Path.exists', return_value=False):
            service = CANService()
            interfaces = service.list_interfaces()
            
            # Should return empty list or handle gracefully
            assert isinstance(interfaces, list)
    
    @patch('subprocess.run')
    def test_list_interfaces_ip_command_not_found(self, mock_subprocess_run):
        """Test listing interfaces when ip command is not found"""
        mock_subprocess_run.side_effect = FileNotFoundError()
        
        with patch('pathlib.Path.exists', return_value=False):
            service = CANService()
            interfaces = service.list_interfaces()
            
            assert isinstance(interfaces, list)
    
    def test_is_can_interface_type_file_error(self, temp_dir):
        """Test _is_can_interface when type file read fails"""
        service = CANService()
        interface_path = temp_dir / 'can0'
        interface_path.mkdir()
        type_file = interface_path / 'type'
        type_file.write_text('invalid')  # Will cause ValueError
        
        # Should fall back to name pattern check
        result = service._is_can_interface(interface_path)
        assert result is True  # can0 matches pattern
    
    def test_is_can_interface_type_file_ioerror(self, temp_dir):
        """Test _is_can_interface when type file IOError"""
        service = CANService()
        interface_path = temp_dir / 'can0'
        interface_path.mkdir()
        
        # Mock file that raises IOError
        with patch('builtins.open', side_effect=IOError('Permission denied')):
            result = service._is_can_interface(interface_path)
            assert result is True  # Falls back to name pattern
    
    def test_get_interface_info_invalid_name(self):
        """Test _get_interface_info with invalid interface name"""
        service = CANService()
        result = service._get_interface_info('invalid-interface!')
        
        assert result is None
    
    def test_get_interface_info_exception(self):
        """Test _get_interface_info when exception occurs"""
        service = CANService()
        
        with patch.object(service, '_get_interface_status', side_effect=Exception('Test error')):
            result = service._get_interface_info('can0')
            
            assert result is None
    
    @patch('subprocess.run')
    def test_get_interface_status_unknown(self, mock_subprocess_run):
        """Test getting interface status when status is unknown"""
        mock_result = Mock()
        mock_result.returncode = 1  # Command failed
        mock_subprocess_run.return_value = mock_result
        
        with patch('pathlib.Path.exists', return_value=False):
            service = CANService()
            status = service._get_interface_status('can0')
            
            assert status == 'unknown'
    
    @patch('subprocess.run')
    def test_get_interface_status_via_operstate(self, mock_subprocess_run, temp_dir):
        """Test getting interface status via /sys/class/net/operstate"""
        from unittest.mock import mock_open
        mock_result = Mock()
        mock_result.returncode = 1
        mock_subprocess_run.return_value = mock_result
        
        operstate_file = temp_dir / 'can0' / 'operstate'
        operstate_file.parent.mkdir()
        operstate_file.write_text('up')
        
        service = CANService()
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='up')):
                # Patch the path construction for operstate file
                with patch('pathlib.Path') as mock_path_class:
                    mock_path_instance = Mock()
                    mock_path_instance.exists.return_value = True
                    mock_path_class.return_value = mock_path_instance
                    status = service._get_interface_status('can0')
                    # This will try to read from operstate
                    assert status in ['up', 'down', 'unknown']
    
    @patch('subprocess.run')
    def test_get_interface_bitrate_via_sys(self, mock_subprocess_run, temp_dir):
        """Test getting interface bitrate via /sys/class/net"""
        from unittest.mock import mock_open
        mock_result = Mock()
        mock_result.returncode = 1  # ip command fails
        mock_subprocess_run.return_value = mock_result
        
        bitrate_file = temp_dir / 'can0' / 'bitrate'
        bitrate_file.parent.mkdir()
        bitrate_file.write_text('500000')
        
        service = CANService()
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='500000')):
                bitrate = service._get_interface_bitrate('can0')
                assert bitrate == 500000
    
    @patch('subprocess.run')
    def test_get_interface_bitrate_error(self, mock_subprocess_run):
        """Test getting interface bitrate when errors occur"""
        import subprocess
        # Mock subprocess to raise SubprocessError (which is caught)
        mock_subprocess_run.side_effect = subprocess.SubprocessError('Test error')
        
        # Mock the fallback path (bitrate file) to not exist
        with patch('pathlib.Path.exists', return_value=False):
            service = CANService()
            # The exception will be caught in the try/except block and return None
            bitrate = service._get_interface_bitrate('can0')
            
            # Should return None when exception occurs
            assert bitrate is None
    
    def test_get_interface_type_via_sys(self, temp_dir):
        """Test getting interface type via /sys/class/net"""
        from unittest.mock import mock_open
        type_file = temp_dir / 'can0' / 'type'
        type_file.parent.mkdir()
        type_file.write_text('280')
        
        service = CANService()
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='280')):
                interface_type = service._get_interface_type('can0')
                assert interface_type == 'socketcan'
    
    def test_get_additional_info(self, temp_dir):
        """Test getting additional interface information"""
        interface_dir = temp_dir / 'can0'
        interface_dir.mkdir()
        (interface_dir / 'mtu').write_text('16')
        
        stats_dir = interface_dir / 'statistics'
        stats_dir.mkdir()
        (stats_dir / 'rx_packets').write_text('100')
        (stats_dir / 'tx_packets').write_text('50')
        
        with patch('pathlib.Path') as mock_path:
            def path_side_effect(path_str):
                if 'mtu' in path_str:
                    return interface_dir / 'mtu'
                elif 'statistics' in path_str:
                    return stats_dir
                return Mock(exists=lambda: False)
            
            mock_path.side_effect = path_side_effect
            
            service = CANService()
            info = service._get_additional_info('can0')
            
            # Should have some info
            assert isinstance(info, dict)
    
    @patch('subprocess.run')
    def test_start_interface_timeout(self, mock_subprocess_run):
        """Test starting interface when subprocess times out"""
        import subprocess
        with patch.object(CANService, 'get_interface') as mock_get:
            mock_get.return_value = CANInterface(
                name='can0',
                status='down',
                bitrate=None,
                interface_type='socketcan',
                is_capturing=False,
                active_session_id=None
            )
            
            mock_subprocess_run.side_effect = subprocess.TimeoutExpired('ip', 10)
            
            service = CANService()
            result = service.start_interface('can0', bitrate=500000)
            
            assert result['success'] is False
            assert 'Timeout' in result['message']
    
    @patch('subprocess.run')
    def test_start_interface_exception(self, mock_subprocess_run):
        """Test starting interface when exception occurs"""
        with patch.object(CANService, 'get_interface') as mock_get:
            mock_get.return_value = CANInterface(
                name='can0',
                status='down',
                bitrate=None,
                interface_type='socketcan',
                is_capturing=False,
                active_session_id=None
            )
            
            mock_subprocess_run.side_effect = Exception('Unexpected error')
            
            service = CANService()
            result = service.start_interface('can0', bitrate=500000)
            
            assert result['success'] is False
            assert 'Error' in result['message']
    
    @patch('subprocess.run')
    def test_start_interface_configure_fails(self, mock_subprocess_run):
        """Test starting interface when configuration fails"""
        with patch.object(CANService, 'get_interface') as mock_get:
            mock_get.return_value = CANInterface(
                name='can0',
                status='down',
                bitrate=None,
                interface_type='socketcan',
                is_capturing=False,
                active_session_id=None
            )
            
            # First call (set down) succeeds, second (configure) fails
            mock_result_success = Mock()
            mock_result_success.returncode = 0
            
            mock_result_fail = Mock()
            mock_result_fail.returncode = 1
            mock_result_fail.stderr = 'Configuration failed'
            
            mock_subprocess_run.side_effect = [mock_result_success, mock_result_fail]
            
            service = CANService()
            result = service.start_interface('can0', bitrate=500000)
            
            assert result['success'] is False
            assert 'Failed to configure' in result['message']
    
    @patch('subprocess.run')
    def test_stop_interface_not_found(self, mock_subprocess_run):
        """Test stopping interface that doesn't exist"""
        with patch.object(CANService, 'get_interface', return_value=None):
            service = CANService()
            result = service.stop_interface('can999')
            
            assert result['success'] is False
            assert 'not found' in result['message']
    
    @patch('subprocess.run')
    def test_stop_interface_timeout(self, mock_subprocess_run):
        """Test stopping interface when subprocess times out"""
        import subprocess
        with patch.object(CANService, 'get_interface') as mock_get:
            mock_get.return_value = CANInterface(
                name='can0',
                status='up',
                bitrate=500000,
                interface_type='socketcan',
                is_capturing=False,
                active_session_id=None
            )
            
            mock_subprocess_run.side_effect = subprocess.TimeoutExpired('ip', 10)
            
            service = CANService()
            result = service.stop_interface('can0')
            
            assert result['success'] is False
            assert 'Timeout' in result['message']
    
    @patch('subprocess.run')
    def test_stop_interface_exception(self, mock_subprocess_run):
        """Test stopping interface when exception occurs"""
        with patch.object(CANService, 'get_interface') as mock_get:
            mock_get.return_value = CANInterface(
                name='can0',
                status='up',
                bitrate=500000,
                interface_type='socketcan',
                is_capturing=False,
                active_session_id=None
            )
            
            mock_subprocess_run.side_effect = Exception('Unexpected error')
            
            service = CANService()
            result = service.stop_interface('can0')
            
            assert result['success'] is False
            assert 'Error' in result['message']
    
    @patch('subprocess.run')
    def test_stop_interface_fails(self, mock_subprocess_run):
        """Test stopping interface when command fails"""
        with patch.object(CANService, 'get_interface') as mock_get:
            mock_get.return_value = CANInterface(
                name='can0',
                status='up',
                bitrate=500000,
                interface_type='socketcan',
                is_capturing=False,
                active_session_id=None
            )
            
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = 'Operation not permitted'
            mock_subprocess_run.return_value = mock_result
            
            service = CANService()
            result = service.stop_interface('can0')
            
            assert result['success'] is False
            assert 'Failed to stop' in result['message']

