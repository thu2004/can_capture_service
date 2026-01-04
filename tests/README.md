# Test Suite for CAN Capture Service

This directory contains the test suite for the CAN Capture Service, using pytest with simulated CAN interfaces and candump.

## Test Structure

- `conftest.py` - Pytest fixtures and configuration
- `test_can_service.py` - Tests for CAN interface service
- `test_capture_service.py` - Tests for capture session management
- `test_can_handler.py` - Tests for CAN handler (candump integration)

## Running Tests

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_can_service.py
```

### Run with Coverage

```bash
pytest --cov=app --cov=worker --cov-report=html
```

Coverage report will be generated in `htmlcov/index.html`

### Run Verbose

```bash
pytest -v
```

## Test Features

### Simulated CAN Interfaces

Tests use mocked `/sys/class/net` structure and `ip` command output to simulate CAN interfaces without requiring actual hardware.

### Mocked candump

The `candump` command is mocked using `unittest.mock` to simulate CAN message capture without requiring the actual `can-utils` package or CAN hardware.

### Fixtures

- `temp_dir` - Temporary directory for test files
- `capture_dir` - Temporary capture directory
- `metadata_dir` - Temporary metadata directory
- `mock_can_interface` - Mock CAN interface data
- `mock_candump_process` - Mock candump subprocess
- `mock_candump_output` - Sample candump output lines
- `session_config` - Default session configuration

## Writing New Tests

When adding new tests:

1. Use the provided fixtures for common test data
2. Mock external dependencies (subprocess, file system)
3. Use descriptive test names following `test_<functionality>_<scenario>` pattern
4. Add docstrings explaining what each test validates

## Test Coverage Goals

- CAN Service: Interface listing, status checking, starting/stopping
- Capture Service: Session management, worker process handling
- CAN Handler: candump integration, process management
- File Service: File operations, metadata handling

