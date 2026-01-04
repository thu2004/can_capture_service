# CAN Capture Service

A web-based service for managing CAN bus capture operations. The system provides a web interface (no authentication required) to control CAN interface capture, view captured files, download/remove files, and monitor CAN interface status.

## Features

- **CAN Interface Management**: List, start, stop, and monitor CAN interfaces
- **Capture Control**: Start and stop CAN capture sessions with configurable rotation
- **File Management**: View, download, and delete captured files with metadata
- **Space Limits & Rotation**: Automatic file rotation with configurable space limits
- **REST API**: Complete REST API for programmatic access
- **Web Interface**: User-friendly web interface built with Flask and Bootstrap
- **Log Viewing**: Built-in log viewer for frontend and backend logs
- **System Status**: Real-time system health and statistics monitoring

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- `can-utils` package (for `candump` command)
  - On Debian/Ubuntu: `sudo apt-get install can-utils`
  - On other Linux distributions: Install the appropriate package for your distribution

### Setup

1. Clone or navigate to the project directory:
```bash
cd can_capture_service
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the service (optional):
   - Edit `config.yaml` to customize settings
   - Default configuration should work for basic setup

4. Run the application:
```bash
python run.py
```

5. Access the web interface:
   - Open browser to `http://localhost:5000`
   - Dashboard and all pages are accessible

## Project Structure

```
can_capture_service/
├── app/                    # Flask application
│   ├── __init__.py         # App factory
│   ├── config.py          # Configuration management
│   ├── routes/            # Route handlers (web and API)
│   ├── services/          # Business logic services
│   ├── models/            # Data models
│   ├── templates/         # Jinja2 templates
│   ├── static/            # Static files (CSS, JS, images)
│   └── utils/             # Utility modules
├── worker/                # CAN capture worker processes
├── storage/               # Captured files and metadata
├── logs/                  # Application logs
├── tests/                 # Test files
├── config.yaml            # Configuration file
├── requirements.txt       # Python dependencies
├── run.py                 # Application entry point
└── README.md              # This file
```

## Configuration

Edit `config.yaml` to customize:

- **Server**: Host, port, debug mode
- **Storage**: Capture directory, space limits, cleanup settings
- **CAN**: Default bitrate, supported interfaces, rotation settings
- **Logging**: Log level, file location, rotation settings

## Development

### Running in Development Mode

Set `debug: true` in `config.yaml` or use:
```bash
FLASK_ENV=development python run.py
```

### Testing

Run the test suite with pytest:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest --cov=app --cov=worker --cov-report=html
```

Coverage report will be generated in `htmlcov/index.html`

For more information about testing, see [tests/README.md](tests/README.md).

## API Documentation

API documentation is available at `/api-docs` when the service is running.

The REST API provides endpoints for:
- Interface management (`/api/interfaces`)
- Capture control (`/api/capture`)
- File operations (`/api/files`)
- System status (`/api/system/status`)
- Log viewing (`/api/logs`)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 CTL Technology AB

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
