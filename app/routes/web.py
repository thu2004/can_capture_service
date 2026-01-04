"""
Web page routes

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
from flask import Blueprint, render_template, current_app
from app.services.can_service import CANService

bp = Blueprint('web', __name__)


def get_can_service():
    """Get CAN service instance"""
    supported_interfaces = current_app.config.get('SUPPORTED_INTERFACES', [])
    return CANService(supported_interfaces=supported_interfaces)


@bp.route('/')
def index():
    """Dashboard/home page"""
    try:
        from app.services.capture_service import CaptureService
        from app.services.file_service import FileService
        
        # Get system status
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        default_rotation = current_app.config['DEFAULT_ROTATION']
        
        # Get CAN interfaces
        can_service = get_can_service()
        interfaces = can_service.list_interfaces()
        
        # Get active captures
        capture_service = CaptureService(capture_dir, metadata_dir, default_rotation)
        active_sessions = capture_service.list_sessions()
        
        # Get file stats
        file_service = FileService(capture_dir, metadata_dir)
        files_result = file_service.list_files(limit=1000)
        disk_usage = file_service.get_disk_usage()
        
        # Calculate totals
        total_messages = sum(s.message_count for s in active_sessions)
        total_file_size = sum(f.get('size_mb', 0) for f in files_result.get('files', []))
        
        return render_template('index.html',
                             interfaces=interfaces,
                             active_sessions=active_sessions,
                             total_files=files_result.get('total', 0),
                             total_messages=total_messages,
                             total_file_size=total_file_size,
                             disk_usage=disk_usage)
    except Exception as e:
        return render_template('index.html',
                             interfaces=[],
                             active_sessions=[],
                             total_files=0,
                             total_messages=0,
                             total_file_size=0,
                             error=str(e))


@bp.route('/interfaces')
def interfaces():
    """CAN interfaces page"""
    try:
        can_service = get_can_service()
        interfaces_list = can_service.list_interfaces()
        return render_template('interfaces.html', interfaces=interfaces_list)
    except Exception as e:
        # If there's an error, still render the page but with empty list
        return render_template('interfaces.html', interfaces=[], error=str(e))


@bp.route('/capture')
def capture():
    """Capture control page"""
    try:
        from app.services.capture_service import CaptureService
        
        # Get available interfaces
        can_service = get_can_service()
        interfaces_list = can_service.list_interfaces()
        
        # Get active capture sessions
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        default_rotation = current_app.config['DEFAULT_ROTATION']
        capture_service = CaptureService(capture_dir, metadata_dir, default_rotation)
        active_sessions = capture_service.list_sessions()
        
        # Get default bitrate
        default_bitrate = current_app.config.get('DEFAULT_BITRATE', 500000)
        
        return render_template('capture.html', 
                             interfaces=interfaces_list,
                             active_sessions=active_sessions,
                             default_bitrate=default_bitrate,
                             default_rotation=default_rotation)
    except Exception as e:
        return render_template('capture.html', 
                             interfaces=[],
                             active_sessions=[],
                             error=str(e))


@bp.route('/files')
def files():
    """Files management page"""
    try:
        from app.services.file_service import FileService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        file_service = FileService(capture_dir, metadata_dir)
        
        # Get files list
        files_result = file_service.list_files(limit=100)
        files_list = files_result.get('files', [])
        
        # Get disk usage
        disk_usage = file_service.get_disk_usage()
        
        return render_template('files.html', 
                             files=files_list,
                             total_files=files_result.get('total', 0),
                             disk_usage=disk_usage)
    except Exception as e:
        return render_template('files.html', 
                             files=[],
                             total_files=0,
                             error=str(e))


@bp.route('/api-docs')
def api_docs():
    """API documentation page"""
    from app.utils.api_docs import API_ENDPOINTS
    return render_template('api_docs.html', endpoints=API_ENDPOINTS)


@bp.route('/logs')
def logs():
    """Log viewer page"""
    return render_template('logs.html')

