"""
Pytest configuration and fixtures for CAN Capture Service tests

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
import pytest
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def capture_dir(temp_dir):
    """Create a temporary capture directory"""
    capture_path = temp_dir / 'captures'
    capture_path.mkdir(parents=True, exist_ok=True)
    return capture_path


@pytest.fixture
def metadata_dir(temp_dir):
    """Create a temporary metadata directory"""
    metadata_path = temp_dir / 'metadata'
    metadata_path.mkdir(parents=True, exist_ok=True)
    return metadata_path


@pytest.fixture
def mock_can_interface():
    """Mock CAN interface data"""
    return {
        'name': 'can0',
        'status': 'up',
        'bitrate': 500000,
        'interface_type': 'socketcan',
        'is_capturing': False,
        'active_session_id': None,
        'info': {'mtu': 16}
    }


@pytest.fixture
def mock_can_interfaces():
    """Mock multiple CAN interfaces"""
    return [
        {
            'name': 'can0',
            'status': 'up',
            'bitrate': 500000,
            'interface_type': 'socketcan',
            'is_capturing': False,
            'active_session_id': None
        },
        {
            'name': 'can1',
            'status': 'down',
            'bitrate': 1000000,
            'interface_type': 'socketcan',
            'is_capturing': False,
            'active_session_id': None
        },
        {
            'name': 'vcan0',
            'status': 'up',
            'bitrate': None,
            'interface_type': 'virtual',
            'is_capturing': False,
            'active_session_id': None
        }
    ]


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for testing"""
    with patch('subprocess.run') as mock_run:
        yield mock_run


@pytest.fixture
def mock_candump_process():
    """Mock candump subprocess.Popen"""
    mock_process = Mock()
    mock_process.poll.return_value = None  # Process is running
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.stdout = Mock()
    mock_process.stderr = Mock()
    return mock_process


@pytest.fixture
def mock_candump_output():
    """Sample candump output lines"""
    return [
        "(000.000000) can0 123#DEADBEEF\n",
        "(000.100000) can0 456#CAFEBABE\n",
        "(000.200000) can0 789#12345678\n",
        "(000.300000) can0 ABC#FEDCBA98\n",
        "(000.400000) can0 DEF#11223344\n"
    ]


@pytest.fixture
def mock_ip_link_output():
    """Mock ip link show output"""
    return """1: can0: <NOARP,UP,LOWER_UP,ECHO> mtu 16 qdisc pfifo_fast state UP mode DEFAULT group default qlen 10
    link/can  promiscuity 0 minmtu 0 maxmtu 0
    can <FD> state ERROR-ACTIVE (berr-counter tx 0 rx 0) restart-ms 0
          bitrate 500000 sample-point 0.875
          tq 125 prop-seg 6 phase-seg1 6 phase-seg2 2 sjw 1
          can0: tseg1 2..64 tseg2 1..32 sjw 1..32 brp 1..1024
"""


@pytest.fixture
def mock_ip_link_list_output():
    """Mock ip link show type can output"""
    return """1: can0: <NOARP,UP,LOWER_UP,ECHO> mtu 16 qdisc pfifo_fast state UP mode DEFAULT group default qlen 10
    link/can
2: can1: <NOARP> mtu 16 qdisc noop state DOWN mode DEFAULT group default qlen 10
    link/can
3: vcan0: <NOARP,UP,LOWER_UP> mtu 72 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/can
"""


@pytest.fixture
def mock_sys_class_net(temp_dir):
    """Create mock /sys/class/net structure"""
    sys_net = temp_dir / 'sys' / 'class' / 'net'
    sys_net.mkdir(parents=True, exist_ok=True)
    
    # Create mock can0 interface
    can0_dir = sys_net / 'can0'
    can0_dir.mkdir()
    (can0_dir / 'type').write_text('280')  # CAN interface type
    (can0_dir / 'operstate').write_text('up')
    (can0_dir / 'bitrate').write_text('500000')
    (can0_dir / 'mtu').write_text('16')
    
    # Create mock can1 interface
    can1_dir = sys_net / 'can1'
    can1_dir.mkdir()
    (can1_dir / 'type').write_text('280')
    (can1_dir / 'operstate').write_text('down')
    (can1_dir / 'bitrate').write_text('1000000')
    (can1_dir / 'mtu').write_text('16')
    
    # Create mock vcan0 interface
    vcan0_dir = sys_net / 'vcan0'
    vcan0_dir.mkdir()
    (vcan0_dir / 'type').write_text('280')
    (vcan0_dir / 'operstate').write_text('up')
    (vcan0_dir / 'mtu').write_text('72')
    
    return sys_net


@pytest.fixture
def default_rotation_config():
    """Default rotation configuration for tests"""
    return {
        'strategy': 'size',
        'max_file_size_mb': 10.0,
        'rotation_action': 'rotate'
    }


@pytest.fixture
def session_config(capture_dir, metadata_dir, default_rotation_config):
    """Default session configuration for tests"""
    return {
        'session_id': 'test-session-123',
        'interface': 'can0',
        'bitrate': 500000,
        'output_file': 'test_capture.log',
        'space_limit_mb': 100.0,
        'rotation': default_rotation_config,
        'capture_dir': str(capture_dir),
        'metadata_dir': str(metadata_dir)
    }

