#!/bin/bash

# Download the latest version of Go
wget https://golang.org/dl/go1.17.6.linux-amd64.tar.gz

# Extract the archive
tar -C /usr/local -xzf go1.17.6.linux-amd64.tar.gz

# Add Go to PATH
echo "export PATH=\$PATH:/usr/local/go/bin" >> ~/.profile

# Apply the changes to PATH
source ~/.profile

# Verify the installation
go version
