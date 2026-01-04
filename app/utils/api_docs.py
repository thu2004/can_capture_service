"""
API documentation metadata and helpers
"""

API_ENDPOINTS = {
    "interfaces": {
        "list": {
            "method": "GET",
            "path": "/api/interfaces",
            "description": "List all available CAN interfaces",
            "request_schema": None,
            "response_schemas": {
                200: {
                    "interfaces": "array of interface objects",
                    "count": "number"
                }
            },
            "examples": {
                "curl": "curl -X GET http://localhost:5000/api/interfaces",
                "python": """import requests
response = requests.get('http://localhost:5000/api/interfaces')
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/interfaces')
  .then(response => response.json())
  .then(data => console.log(data));"""
            }
        },
        "get": {
            "method": "GET",
            "path": "/api/interfaces/<name>",
            "description": "Get specific interface information",
            "request_schema": {
                "path_params": {
                    "name": "string - Interface name (e.g., 'can0')"
                }
            },
            "response_schemas": {
                200: {
                    "name": "string",
                    "status": "string (up/down/unknown)",
                    "bitrate": "integer",
                    "type": "string"
                },
                404: {"error": "string"}
            },
            "examples": {
                "curl": "curl -X GET http://localhost:5000/api/interfaces/can0",
                "python": """import requests
response = requests.get('http://localhost:5000/api/interfaces/can0')
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/interfaces/can0')
  .then(response => response.json())
  .then(data => console.log(data));"""
            }
        },
        "start": {
            "method": "POST",
            "path": "/api/interfaces/<name>/start",
            "description": "Start/bring up a CAN interface",
            "request_schema": {
                "path_params": {
                    "name": "string - Interface name"
                },
                "body": {
                    "bitrate": "integer (optional) - Bitrate in bps"
                }
            },
            "response_schemas": {
                200: {
                    "success": True,
                    "message": "string",
                    "interface": "string"
                },
                400: {
                    "success": False,
                    "message": "string"
                }
            },
            "examples": {
                "curl": """curl -X POST http://localhost:5000/api/interfaces/can0/start \\
  -H "Content-Type: application/json" \\
  -d '{"bitrate": 500000}'""",
                "python": """import requests
response = requests.post(
    'http://localhost:5000/api/interfaces/can0/start',
    json={'bitrate': 500000}
)
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/interfaces/can0/start', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({bitrate: 500000})
})
.then(response => response.json())
.then(data => console.log(data));"""
            }
        },
        "stop": {
            "method": "POST",
            "path": "/api/interfaces/<name>/stop",
            "description": "Stop/bring down a CAN interface",
            "request_schema": {
                "path_params": {
                    "name": "string - Interface name"
                }
            },
            "response_schemas": {
                200: {
                    "success": True,
                    "message": "string"
                }
            },
            "examples": {
                "curl": "curl -X POST http://localhost:5000/api/interfaces/can0/stop",
                "python": """import requests
response = requests.post('http://localhost:5000/api/interfaces/can0/stop')
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/interfaces/can0/stop', {
  method: 'POST'
})
.then(response => response.json())
.then(data => console.log(data));"""
            }
        }
    },
    "capture": {
        "start": {
            "method": "POST",
            "path": "/api/capture/start",
            "description": "Start a new CAN capture session",
            "request_schema": {
                "body": {
                    "interface": "string (required) - CAN interface name",
                    "bitrate": "integer (optional) - Bitrate in bps",
                    "output_file": "string (optional) - Output filename",
                    "space_limit_mb": "number (optional) - Space limit in MB",
                    "rotation": {
                        "strategy": "string (size/time/count)",
                        "max_file_size_mb": "number",
                        "rotation_action": "string (rotate/stop/delete_oldest)"
                    }
                }
            },
            "response_schemas": {
                200: {
                    "success": True,
                    "session_id": "string",
                    "interface": "string",
                    "status": "string",
                    "output_file": "string",
                    "start_time": "string"
                },
                400: {
                    "success": False,
                    "error": "string"
                }
            },
            "examples": {
                "curl": """curl -X POST http://localhost:5000/api/capture/start \\
  -H "Content-Type: application/json" \\
  -d '{
    "interface": "can0",
    "bitrate": 500000,
    "space_limit_mb": 100
  }'""",
                "python": """import requests
response = requests.post(
    'http://localhost:5000/api/capture/start',
    json={
        'interface': 'can0',
        'bitrate': 500000,
        'space_limit_mb': 100
    }
)
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/capture/start', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    interface: 'can0',
    bitrate: 500000,
    space_limit_mb: 100
  })
})
.then(response => response.json())
.then(data => console.log(data));"""
            }
        },
        "stop": {
            "method": "POST",
            "path": "/api/capture/stop",
            "description": "Stop a capture session",
            "request_schema": {
                "body": {
                    "session_id": "string (required) - Session ID"
                }
            },
            "response_schemas": {
                200: {
                    "success": True,
                    "message": "string"
                }
            },
            "examples": {
                "curl": """curl -X POST http://localhost:5000/api/capture/stop \\
  -H "Content-Type: application/json" \\
  -d '{"session_id": "uuid"}'""",
                "python": """import requests
response = requests.post(
    'http://localhost:5000/api/capture/stop',
    json={'session_id': 'uuid'}
)
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/capture/stop', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({session_id: 'uuid'})
})
.then(response => response.json())
.then(data => console.log(data));"""
            }
        },
        "status": {
            "method": "GET",
            "path": "/api/capture/status",
            "description": "Get all active capture sessions",
            "response_schemas": {
                200: {
                    "sessions": "array of session objects",
                    "count": "number"
                }
            },
            "examples": {
                "curl": "curl -X GET http://localhost:5000/api/capture/status",
                "python": """import requests
response = requests.get('http://localhost:5000/api/capture/status')
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/capture/status')
  .then(response => response.json())
  .then(data => console.log(data));"""
            }
        }
    },
    "files": {
        "list": {
            "method": "GET",
            "path": "/api/files",
            "description": "List all captured files",
            "request_schema": {
                "query_params": {
                    "interface": "string (optional) - Filter by interface",
                    "limit": "integer (optional, default: 50)",
                    "offset": "integer (optional, default: 0)"
                }
            },
            "response_schemas": {
                200: {
                    "files": "array of file objects",
                    "total": "number",
                    "count": "number"
                }
            },
            "examples": {
                "curl": "curl -X GET 'http://localhost:5000/api/files?interface=can0&limit=50'",
                "python": """import requests
response = requests.get('http://localhost:5000/api/files', params={'interface': 'can0', 'limit': 50})
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/files?interface=can0&limit=50')
  .then(response => response.json())
  .then(data => console.log(data));"""
            }
        },
        "download": {
            "method": "GET",
            "path": "/api/files/<filename>/download",
            "description": "Download a captured file",
            "request_schema": {
                "path_params": {
                    "filename": "string - Filename"
                }
            },
            "response_schemas": {
                200: "File download",
                404: {"error": "string"}
            },
            "examples": {
                "curl": "curl -X GET http://localhost:5000/api/files/capture_can0_20240101.log/download -o output.log",
                "python": """import requests
response = requests.get('http://localhost:5000/api/files/capture_can0_20240101.log/download')
with open('output.log', 'wb') as f:
    f.write(response.content)""",
                "javascript": """fetch('http://localhost:5000/api/files/capture_can0_20240101.log/download')
  .then(response => response.blob())
  .then(blob => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'capture.log';
    a.click();
  });"""
            }
        },
        "delete": {
            "method": "DELETE",
            "path": "/api/files/<filename>",
            "description": "Delete a captured file",
            "request_schema": {
                "path_params": {
                    "filename": "string - Filename"
                }
            },
            "response_schemas": {
                200: {
                    "success": True,
                    "message": "string"
                },
                400: {
                    "success": False,
                    "error": "string"
                }
            },
            "examples": {
                "curl": "curl -X DELETE http://localhost:5000/api/files/capture_can0_20240101.log",
                "python": """import requests
response = requests.delete('http://localhost:5000/api/files/capture_can0_20240101.log')
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/files/capture_can0_20240101.log', {
  method: 'DELETE'
})
.then(response => response.json())
.then(data => console.log(data));"""
            }
        }
    },
    "system": {
        "status": {
            "method": "GET",
            "path": "/api/system/status",
            "description": "Get system health and statistics",
            "response_schemas": {
                200: {
                    "status": "string",
                    "disk_usage": "object",
                    "files": "object",
                    "captures": "object",
                    "interfaces": "object"
                }
            },
            "examples": {
                "curl": "curl -X GET http://localhost:5000/api/system/status",
                "python": """import requests
response = requests.get('http://localhost:5000/api/system/status')
print(response.json())""",
                "javascript": """fetch('http://localhost:5000/api/system/status')
  .then(response => response.json())
  .then(data => console.log(data));"""
            }
        }
    }
}
