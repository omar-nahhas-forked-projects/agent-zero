FROM continuumio/miniconda3:latest

# Build arguments with defaults
ARG ENABLE_GPU=false
ARG CUDA_VERSION=12.1
ARG FAISS_VERSION=1.9.0

# Set environment variables from build args
ENV ENABLE_GPU=$ENABLE_GPU \
    CUDA_VERSION=$CUDA_VERSION \
    FAISS_VERSION=$FAISS_VERSION

# Install system packages
RUN set -x && \
    apt-get update && export DEBIAN_FRONTEND=noninteractive && \
    apt-get -y install --no-install-recommends \
    git \
    curl \
    wget \
    ca-certificates \
    sudo \
    openssh-client \
    gnupg2 \
    lsb-release \
    bash \
    bash-builtins \
    ssh && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/*

# If GPU is enabled, install NVIDIA container toolkit dependencies
RUN set -x && \
    if [ "$ENABLE_GPU" = "true" ]; then \
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg && \
        curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list && \
        apt-get update && \
        apt-get install -y nvidia-container-toolkit && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# Copy and run setup script with verbose output
COPY setup.sh /tmp/
RUN set -x && \
    chmod +x /tmp/setup.sh && \
    bash -x /tmp/setup.sh