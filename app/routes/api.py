"""
REST API routes

Copyright (c) 2026 CTL Technology AB
Licensed under the MIT License
"""
from flask import Blueprint, jsonify, current_app
from datetime import datetime
from pathlib import Path
from app.services.can_service import CANService
from app.utils.logger import get_logger

bp = Blueprint('api', __name__)
logger = get_logger(__name__, log_type='frontend')


def get_can_service():
    """Get CAN service instance"""
    supported_interfaces = current_app.config.get('SUPPORTED_INTERFACES', [])
    return CANService(supported_interfaces=supported_interfaces)


@bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'CAN Capture Service'
    }), 200


@bp.route('/interfaces', methods=['GET'])
def list_interfaces():
    """List all available CAN interfaces"""
    try:
        can_service = get_can_service()
        interfaces = can_service.list_interfaces()
        
        return jsonify({
            'interfaces': [iface.to_dict() for iface in interfaces],
            'count': len(interfaces)
        }), 200
    except Exception as e:
        logger.error(f'Error listing interfaces: {e}')
        return jsonify({
            'error': 'Failed to list interfaces',
            'message': str(e)
        }), 500


@bp.route('/interfaces/<name>', methods=['GET'])
def get_interface(name):
    """Get specific interface information"""
    try:
        can_service = get_can_service()
        interface = can_service.get_interface(name)
        
        if interface:
            return jsonify(interface.to_dict()), 200
        else:
            return jsonify({
                'error': 'Interface not found',
                'name': name
            }), 404
    except Exception as e:
        logger.error(f'Error getting interface {name}: {e}')
        return jsonify({
            'error': 'Failed to get interface',
            'message': str(e)
        }), 500


@bp.route('/interfaces/<name>/status', methods=['GET'])
def get_interface_status(name):
    """Get status of specific interface"""
    try:
        can_service = get_can_service()
        interface = can_service.get_interface(name)
        
        if interface:
            return jsonify({
                'name': interface.name,
                'status': interface.status,
                'is_capturing': interface.is_capturing,
                'active_session_id': interface.active_session_id
            }), 200
        else:
            return jsonify({
                'error': 'Interface not found',
                'name': name
            }), 404
    except Exception as e:
        logger.error(f'Error getting interface status {name}: {e}')
        return jsonify({
            'error': 'Failed to get interface status',
            'message': str(e)
        }), 500


@bp.route('/interfaces/<name>/info', methods=['GET'])
def get_interface_info(name):
    """Get detailed information about interface"""
    try:
        can_service = get_can_service()
        interface = can_service.get_interface(name)
        
        if interface:
            return jsonify(interface.to_dict()), 200
        else:
            return jsonify({
                'error': 'Interface not found',
                'name': name
            }), 404
    except Exception as e:
        logger.error(f'Error getting interface info {name}: {e}')
        return jsonify({
            'error': 'Failed to get interface info',
            'message': str(e)
        }), 500


@bp.route('/interfaces/<name>/start', methods=['POST'])
def start_interface(name):
    """Start/bring up a CAN interface"""
    try:
        from flask import request
        can_service = get_can_service()
        
        # Get optional bitrate from request, or use default from config
        data = request.get_json() or {}
        bitrate = data.get('bitrate')
        default_bitrate = current_app.config.get('DEFAULT_BITRATE', 500000)
        
        result = can_service.start_interface(name, bitrate=bitrate, default_bitrate=default_bitrate)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f'Error starting interface {name}: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to start interface',
            'message': str(e)
        }), 500


@bp.route('/interfaces/<name>/stop', methods=['POST'])
def stop_interface(name):
    """Stop/bring down a CAN interface"""
    try:
        can_service = get_can_service()
        result = can_service.stop_interface(name)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f'Error stopping interface {name}: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to stop interface',
            'message': str(e)
        }), 500


@bp.route('/capture/start', methods=['POST'])
def start_capture():
    """Start a new capture session"""
    try:
        from flask import request
        from app.services.capture_service import CaptureService
        
        data = request.get_json() or {}
        interface = data.get('interface')
        
        if not interface:
            return jsonify({
                'success': False,
                'error': 'Interface is required'
            }), 400
        
        # Get capture service
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        default_rotation = current_app.config['DEFAULT_ROTATION']
        capture_service = CaptureService(capture_dir, metadata_dir, default_rotation)
        
        # Start capture
        result = capture_service.start_capture(
            interface=data.get('interface'),
            bitrate=data.get('bitrate'),
            output_file=data.get('output_file'),
            space_limit_mb=data.get('space_limit_mb'),
            rotation=data.get('rotation')
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f'Error starting capture: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to start capture',
            'message': str(e)
        }), 500


@bp.route('/capture/stop', methods=['POST'])
def stop_capture():
    """Stop a capture session"""
    try:
        from flask import request
        from app.services.capture_service import CaptureService
        
        data = request.get_json() or {}
        session_id = data.get('session_id')
        
        logger.info(f'Stop capture request received for session: {session_id}')
        
        if not session_id:
            logger.warning('Stop capture request missing session_id')
            return jsonify({
                'success': False,
                'error': 'session_id is required'
            }), 400
        
        # Get capture service
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        default_rotation = current_app.config['DEFAULT_ROTATION']
        capture_service = CaptureService(capture_dir, metadata_dir, default_rotation)
        
        # Stop capture
        logger.info(f'Calling capture_service.stop_capture for session: {session_id}')
        result = capture_service.stop_capture(session_id)
        logger.info(f'Stop capture result: success={result.get("success")}, error={result.get("error")}')
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            logger.warning(f'Stop capture failed: {result.get("error")}')
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f'Error stopping capture: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to stop capture',
            'message': str(e)
        }), 500


@bp.route('/capture/status', methods=['GET'])
def get_capture_status():
    """Get all active capture sessions"""
    try:
        from app.services.capture_service import CaptureService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        default_rotation = current_app.config['DEFAULT_ROTATION']
        capture_service = CaptureService(capture_dir, metadata_dir, default_rotation)
        
        sessions = capture_service.list_sessions()
        
        return jsonify({
            'sessions': [s.to_dict() for s in sessions],
            'count': len(sessions)
        }), 200
        
    except Exception as e:
        logger.error(f'Error getting capture status: {e}')
        return jsonify({
            'error': 'Failed to get capture status',
            'message': str(e)
        }), 500


@bp.route('/capture/status/<session_id>', methods=['GET'])
def get_session_status(session_id):
    """Get specific capture session status"""
    try:
        from app.services.capture_service import CaptureService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        default_rotation = current_app.config['DEFAULT_ROTATION']
        capture_service = CaptureService(capture_dir, metadata_dir, default_rotation)
        
        status = capture_service.get_session_status(session_id)
        
        if status:
            return jsonify(status), 200
        else:
            return jsonify({
                'error': 'Session not found',
                'session_id': session_id
            }), 404
            
    except Exception as e:
        logger.error(f'Error getting session status: {e}')
        return jsonify({
            'error': 'Failed to get session status',
            'message': str(e)
        }), 500


@bp.route('/capture/cleanup', methods=['POST'])
def cleanup_inactive_sessions():
    """Clean up inactive (stopped/error) capture sessions"""
    try:
        from flask import request
        from app.services.capture_service import CaptureService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        default_rotation = current_app.config['DEFAULT_ROTATION']
        capture_service = CaptureService(capture_dir, metadata_dir, default_rotation)
        
        # Get optional parameters
        data = request.get_json() or {}
        older_than_hours = data.get('older_than_hours', 24)
        remove_all_errors = data.get('remove_all_errors', True)  # Default to True to remove all errors
        
        result = capture_service.cleanup_inactive_sessions(
            older_than_hours=older_than_hours,
            remove_all_errors=remove_all_errors
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f'Error cleaning up sessions: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to cleanup sessions',
            'message': str(e)
        }), 500


@bp.route('/files', methods=['GET'])
def list_files():
    """List all captured files"""
    try:
        from flask import request
        from app.services.file_service import FileService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        file_service = FileService(capture_dir, metadata_dir)
        
        # Get query parameters
        interface = request.args.get('interface')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        result = file_service.list_files(interface=interface, limit=limit, offset=offset)
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f'Error listing files: {e}')
        return jsonify({
            'error': 'Failed to list files',
            'message': str(e)
        }), 500


@bp.route('/files/<filename>/info', methods=['GET'])
def get_file_info(filename):
    """Get file metadata"""
    try:
        from app.services.file_service import FileService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        file_service = FileService(capture_dir, metadata_dir)
        
        file_info = file_service.get_file_info(filename)
        
        if file_info:
            return jsonify(file_info), 200
        else:
            return jsonify({
                'error': 'File not found',
                'filename': filename
            }), 404
            
    except Exception as e:
        logger.error(f'Error getting file info: {e}')
        return jsonify({
            'error': 'Failed to get file info',
            'message': str(e)
        }), 500


@bp.route('/files/<filename>/view', methods=['GET'])
def view_file(filename):
    """View file content - returns last N lines for live viewing"""
    try:
        from flask import request
        from app.services.file_service import FileService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        file_service = FileService(capture_dir, metadata_dir)
        
        file_path = file_service.get_file_path(filename)
        
        if not file_path or not file_path.exists():
            return jsonify({
                'error': 'File not found',
                'filename': filename
            }), 404
        
        lines = int(request.args.get('lines', 100))
        max_lines = 10000  # Maximum lines to return
        
        if lines > max_lines:
            lines = max_lines
        
        # Read last N lines from file
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                content = ''.join(last_lines)
        except Exception as e:
            logger.error(f'Error reading file {filename}: {e}')
            return jsonify({
                'error': 'Failed to read file',
                'message': str(e)
            }), 500
        
        return jsonify({
            'filename': filename,
            'content': content,
            'total_lines': len(all_lines),
            'returned_lines': len(last_lines),
            'file_size_mb': file_path.stat().st_size / (1024 * 1024)
        }), 200
            
    except Exception as e:
        logger.error(f'Error viewing file {filename}: {e}')
        return jsonify({
            'error': 'Failed to view file',
            'message': str(e)
        }), 500


@bp.route('/files/<filename>/download', methods=['GET'])
def download_file(filename):
    """Download a captured file"""
    try:
        from flask import send_file
        from app.services.file_service import FileService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        file_service = FileService(capture_dir, metadata_dir)
        
        file_path = file_service.get_file_path(filename)
        
        if file_path:
            return send_file(
                str(file_path),
                as_attachment=True,
                download_name=filename
            ), 200
        else:
            return jsonify({
                'error': 'File not found',
                'filename': filename
            }), 404
            
    except Exception as e:
        logger.error(f'Error downloading file: {e}')
        return jsonify({
            'error': 'Failed to download file',
            'message': str(e)
        }), 500


@bp.route('/files/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete a captured file"""
    try:
        from app.services.file_service import FileService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        file_service = FileService(capture_dir, metadata_dir)
        
        result = file_service.delete_file(filename)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f'Error deleting file: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to delete file',
            'message': str(e)
        }), 500


@bp.route('/system/status', methods=['GET'])
def get_system_status():
    """Get system health and statistics"""
    try:
        from app.services.file_service import FileService
        from app.services.capture_service import CaptureService
        
        capture_dir = current_app.config['CAPTURE_DIR']
        metadata_dir = current_app.config['METADATA_DIR']
        default_rotation = current_app.config['DEFAULT_ROTATION']
        
        # Get file service stats
        file_service = FileService(capture_dir, metadata_dir)
        disk_usage = file_service.get_disk_usage()
        files_list = file_service.list_files(limit=1000)
        
        # Get capture service stats
        capture_service = CaptureService(capture_dir, metadata_dir, default_rotation)
        active_sessions = capture_service.list_sessions()
        
        # Get CAN interface stats
        can_service = get_can_service()
        interfaces = can_service.list_interfaces()
        
        return jsonify({
            'status': 'ok',
            'disk_usage': disk_usage,
            'files': {
                'total': files_list.get('total', 0),
                'total_size_gb': sum(f.get('size_mb', 0) for f in files_list.get('files', [])) / 1024
            },
            'captures': {
                'active_sessions': len(active_sessions),
                'total_messages': sum(s.message_count for s in active_sessions)
            },
            'interfaces': {
                'total': len(interfaces),
                'up': len([i for i in interfaces if i.status == 'up']),
                'down': len([i for i in interfaces if i.status == 'down'])
            },
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f'Error getting system status: {e}')
        return jsonify({
            'status': 'error',
            'error': 'Failed to get system status',
            'message': str(e)
        }), 500


@bp.route('/logs/tail', methods=['GET'])
def tail_logs():
    """Tail log file - returns last N lines"""
    try:
        from flask import request
        
        # Get log type (frontend or backend), default to frontend
        log_type = request.args.get('type', 'frontend')
        if log_type not in ['frontend', 'backend']:
            log_type = 'frontend'
        
        # Get appropriate log file based on type
        if log_type == 'frontend':
            log_file = Path(current_app.config.get('LOG_FILE', './logs/frontend.log'))
            max_size_mb = current_app.config.get('LOG_MAX_SIZE_MB', 100)
        else:
            log_file = Path(current_app.config.get('BACKEND_LOG_FILE', './logs/backend.log'))
            # Get backend max size from config
            try:
                from app.config import Config
                config_data = Config._load_config()
                backend_logging = config_data.get('logging', {}).get('backend', {})
                max_size_mb = backend_logging.get('max_size_mb', 100)
            except Exception:
                max_size_mb = 100
        
        lines = int(request.args.get('lines', 100))
        max_lines = 10000  # Maximum lines to return
        
        if lines > max_lines:
            lines = max_lines
        
        # Create log file and directory if they don't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)
        if not log_file.exists():
            # Create empty log file
            log_file.touch()
        
        if not log_file.exists():
            return jsonify({
                'error': 'Log file not found and could not be created',
                'path': str(log_file),
                'type': log_type
            }), 404
        
        # Read last N lines from file
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return jsonify({
            'lines': last_lines,
            'total_lines': len(all_lines),
            'returned_lines': len(last_lines),
            'file_size_mb': log_file.stat().st_size / (1024 * 1024),
            'type': log_type,
            'max_size_mb': max_size_mb
        }), 200
        
    except Exception as e:
        logger.error(f'Error tailing logs: {e}')
        return jsonify({
            'error': 'Failed to tail logs',
            'message': str(e)
        }), 500


@bp.route('/logs/clean', methods=['POST'])
def clean_logs():
    """Clean (truncate) log file"""
    try:
        from flask import request
        
        # Get log type (frontend or backend), default to frontend
        log_type = request.args.get('type', 'frontend')
        if log_type not in ['frontend', 'backend']:
            log_type = 'frontend'
        
        # Get appropriate log file based on type
        if log_type == 'frontend':
            log_file = Path(current_app.config.get('LOG_FILE', './logs/frontend.log'))
        else:
            log_file = Path(current_app.config.get('BACKEND_LOG_FILE', './logs/backend.log'))
        
        # Create log file and directory if they don't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Truncate the log file (clear all contents)
        try:
            with open(log_file, 'w') as f:
                f.write('')
            
            logger.info(f'Log file cleaned: {log_file} (type: {log_type})')
            
            return jsonify({
                'success': True,
                'message': 'Log file cleaned successfully',
                'path': str(log_file),
                'type': log_type
            }), 200
        except PermissionError:
            return jsonify({
                'success': False,
                'error': 'Permission denied. Cannot write to log file.'
            }), 403
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to clean log file: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.error(f'Error cleaning log file: {e}')
        return jsonify({
            'success': False,
            'error': 'Failed to clean log file',
            'message': str(e)
        }), 500

