#!/bin/bash
#
# Install systemd service to enable CAN interfaces at startup
#

set -e

SERVICE_NAME="enable-can-interfaces"
SERVICE_FILE="enable-can-interfaces.service"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

echo "Installing ${SERVICE_NAME} systemd service..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Copy service file
echo "Copying service file to ${SERVICE_PATH}..."
cp "${PROJECT_DIR}/${SERVICE_FILE}" "${SERVICE_PATH}"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable service to start on boot
echo "Enabling service to start on boot..."
systemctl enable "${SERVICE_NAME}.service"

echo ""
echo "Service installed successfully!"
echo ""
echo "To start the service now, run:"
echo "  sudo systemctl start ${SERVICE_NAME}"
echo ""
echo "To check service status, run:"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo ""
echo "To view logs, run:"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
echo "Note: This service will start before can-capture-service to ensure"
echo "      CAN interfaces are available when the capture service starts."

