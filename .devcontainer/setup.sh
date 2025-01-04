#!/bin/bash
set -e

# Install development tools and Python packages
conda install -y -c conda-forge \
    ipython \
    requests \
    black \
    pylint \
    pytest \
    jupyter \
    nodejs
    
conda clean -afy

# Initialize conda in shell
conda init bash
echo 'eval "$(conda shell.bash hook)"' >> /root/.bashrc
echo 'conda activate base' >> /root/.bashrc
