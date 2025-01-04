FROM continuumio/miniconda3:latest

# Install system packages
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive && \
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

COPY setup.sh /tmp/
RUN chmod +x /tmp/setup.sh && /tmp/setup.sh