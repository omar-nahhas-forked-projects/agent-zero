#!/bin/bash

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Install the service
echo "Installing agent-zero-dev service..."
sudo cp "${SCRIPT_DIR}/agent-zero-dev.service" /etc/systemd/system/

# Make the container management script executable
echo "Setting up container management script..."
chmod +x "${SCRIPT_DIR}/start-dev-container.sh"

# Reload systemd daemon
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable and start the service
echo "Enabling and starting the service..."
sudo systemctl enable agent-zero-dev
sudo systemctl restart agent-zero-dev

echo "Installation complete. Check service status with: sudo systemctl status agent-zero-dev"
