#!/bin/bash
set -e

echo "Starting setup.sh..."

# Default values for parameters
ENABLE_GPU=${ENABLE_GPU:-false}
CUDA_VERSION=${CUDA_VERSION:-"12.1"}
FAISS_VERSION=${FAISS_VERSION:-"1.9.0"}

# Convert CUDA_VERSION to PyTorch format (e.g., 12.1 -> cu121)
CUDA_VERSION_PYTORCH="cu$(echo $CUDA_VERSION | sed 's/\.//g')"

echo "Configuration:"
echo "ENABLE_GPU=$ENABLE_GPU"
echo "CUDA_VERSION=$CUDA_VERSION"
echo "CUDA_VERSION_PYTORCH=$CUDA_VERSION_PYTORCH"
echo "FAISS_VERSION=$FAISS_VERSION"

# Install system dependencies
echo "Installing system dependencies..."
apt-get update && export DEBIAN_FRONTEND=noninteractive
apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    python3-dev \
    build-essential

# Install development tools and Python packages
echo "Installing conda packages..."
conda install -y -c conda-forge \
    ipython \
    requests \
    black \
    pylint \
    pytest \
    jupyter \
    nodejs || { echo "Failed to install conda packages"; exit 1; }

# Clean conda cache
echo "Cleaning conda cache..."
conda clean -afy || { echo "Failed to clean conda cache"; exit 1; }

# Initialize conda in shell
echo "Initializing conda..."
conda init bash || { echo "Failed to initialize conda"; exit 1; }
echo 'eval "$(conda shell.bash hook)"' >> /root/.bashrc
echo 'conda activate base' >> /root/.bashrc

# Function to check if NVIDIA GPU is available
check_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi &> /dev/null
        return $?
    else
        return 1
    fi
}

# Install PyTorch and related ML packages
echo "Installing PyTorch and ML packages..."
if [ "$ENABLE_GPU" = "true" ] && check_gpu; then
    echo "Installing PyTorch with GPU support for CUDA $CUDA_VERSION (PyTorch format: $CUDA_VERSION_PYTORCH)..."
    pip install torch==2.2.0 --index-url "https://download.pytorch.org/whl/${CUDA_VERSION_PYTORCH}"
else
    echo "Installing PyTorch CPU version..."
    pip install torch==2.2.0 --index-url https://download.pytorch.org/whl/cpu
fi

# Install other ML and system-dependent packages
echo "Installing ML and system-dependent packages..."
pip install \
    sentence-transformers==3.0.1 \
    lxml_html_clean==0.3.1 \
    newspaper3k==0.2.8 \
    unstructured==0.15.13 \
    unstructured-client==0.25.9 \
    openai-whisper==20240930

# Download NLTK data for newspaper3k
python3 -c "import nltk; nltk.download('punkt')"

# Install FAISS
if [ "$ENABLE_GPU" = "true" ]; then
    echo "GPU support requested..."
    
    if check_gpu; then
        echo "NVIDIA GPU detected. Installing CUDA dependencies..."
        
        # Install CUDA toolkit
        conda install -y -c nvidia cuda-toolkit="$CUDA_VERSION" || { echo "Failed to install CUDA toolkit"; exit 1; }
        
        # Try to install FAISS with GPU support
        if conda install -y -c conda-forge faiss-gpu="$FAISS_VERSION"; then
            echo "Successfully installed FAISS with GPU support"
            # Add CUDA environment variables
            echo 'export PATH=/usr/local/cuda/bin:$PATH' >> /root/.bashrc
            echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> /root/.bashrc
        else
            echo "Failed to install FAISS with GPU support. Falling back to CPU version..."
            pip install "faiss-cpu==$FAISS_VERSION.post1" || { echo "Failed to install FAISS CPU version"; exit 1; }
        fi
    else
        echo "No NVIDIA GPU detected. Installing CPU version of FAISS..."
        pip install "faiss-cpu==$FAISS_VERSION.post1" || { echo "Failed to install FAISS CPU version"; exit 1; }
    fi
else
    echo "Installing CPU version of FAISS..."
    pip install "faiss-cpu==$FAISS_VERSION.post1" || { echo "Failed to install FAISS CPU version"; exit 1; }
fi

# Print configuration summary
echo "Installation completed with the following configuration:"
echo "GPU Support: $ENABLE_GPU"
echo "CUDA Version: $CUDA_VERSION"
echo "PyTorch CUDA Version: $CUDA_VERSION_PYTORCH"
echo "FAISS Version: $FAISS_VERSION"
if [ "$ENABLE_GPU" = "true" ] && check_gpu; then
    nvidia-smi
    python3 -c "import faiss; print(f'FAISS GPU available: {faiss.get_num_gpus() > 0}')"
fi

echo "Setup completed successfully!"
