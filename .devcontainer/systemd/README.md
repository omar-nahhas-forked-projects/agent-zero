# Development Container Systemd Service

This directory contains the necessary files to run the Agent Zero development container as a systemd service.

## Files

- `agent-zero-dev.service`: Systemd service definition file
- `start-dev-container.sh`: Container management script that handles container lifecycle
- `install-service.sh`: Installation script
- `config.env`: Configuration file for data directory paths

## Configuration

The `config.env` file contains the paths for important data directories:
- `KNOWLEDGE_DIR`: Path to the knowledge base directory
- `INSTRUCTIONS_DIR`: Path to the instructions directory
- `MEMORY_DIR`: Path to the memory directory

These directories are mounted in the container at:
- `/workspaces/knowledge`
- `/workspaces/instructions`
- `/workspaces/memory`

## Installation

To install the service:

```bash
# Make the installation script executable if it isn't already
chmod +x install-service.sh

# Run the installation script
./install-service.sh
```

## Usage

After installation, you can manage the service using standard systemd commands:

```bash
# Check service status
sudo systemctl status agent-zero-dev

# Start the service
sudo systemctl start agent-zero-dev

# Stop the service
sudo systemctl stop agent-zero-dev

# Restart the service
sudo systemctl restart agent-zero-dev

# View service logs
sudo journalctl -u agent-zero-dev
```

## Features

- Automatically starts on system boot
- Gracefully handles existing containers
- Monitors container health and restarts if needed
- Preserves container state across service restarts
- Mounts data directories with proper caching for performance
