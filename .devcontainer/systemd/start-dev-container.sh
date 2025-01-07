#!/bin/bash

# Load configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "${SCRIPT_DIR}/config.env"

# Get the project name from the workspace directory
CONTAINER_NAME="agent-zero-dev"
WORKSPACE_DIR="/home/omar/src/github.com/omar-nahhas-forked-projects/agent-zero"
PROJECT_NAME="$(basename ${WORKSPACE_DIR})"
IMAGE_NAME="vsc-agent-zero-a133f0eb029afbffbb315d79c110964cf105f38f44e67c2250393b5b7e0e289c"

# Check if container exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    # Container exists, check if it's running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        # Container exists but is not running, start it
        docker start ${CONTAINER_NAME}
    else
        # Container is already running, do nothing
        echo "Container ${CONTAINER_NAME} is already running"
    fi
else
    # Container doesn't exist, create and start it
    docker run --name ${CONTAINER_NAME} \
        --gpus all \
        -p 80:80 \
        -v ${WORKSPACE_DIR}:/workspaces/${PROJECT_NAME}:cached \
        -v ${KNOWLEDGE_DIR}:${CONTAINER_KNOWLEDGE_DIR}:cached \
        -v ${INSTRUCTIONS_DIR}:${CONTAINER_INSTRUCTIONS_DIR}:cached \
        -v ${MEMORY_DIR}:${CONTAINER_MEMORY_DIR}:cached \
        ${IMAGE_NAME}
fi

# Keep the script running to maintain the service
while true; do
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Container stopped unexpectedly, exiting..."
        exit 1
    fi
    sleep 5
done
