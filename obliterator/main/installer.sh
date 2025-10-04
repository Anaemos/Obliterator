#!/bin/bash
# installer.sh - (Version 4 - Comprehensive)
# Installs all dependencies for Obliterator, including core wiping utilities.

echo "--- Starting Obliterator Dependency Installation ---"

# 1. Update package lists
echo "Updating package lists..."
apt-get update

# 2. Install Core Wiping & Hardware Utilities
echo "Installing core wiping utilities..."
# hdparm & nvme-cli: For hardware-specific commands
# smartmontools: For reading device serial numbers and health
# coreutils: Provides critical commands like 'dd' and 'shred'
# util-linux: Provides 'blockdev'
# pv: Provides the pipe viewer for the progress bar
apt-get install -y hdparm nvme-cli smartmontools coreutils util-linux pv dmidecode

# 3. Install Python Environment and GUI Toolkit
echo "Installing Python and GUI tools..."
apt-get install -y python3 python3-pip python3-tk

echo "Installing Python and GUI tools..."
# python3-pil & python3-pil.imagetk are required for logo support
apt-get install -y python3 python3-pip python3-tk python3-pil python3-pil.imagetk

# 4. Install Required Python Libraries
echo "Installing Python libraries..."
# Use apt for cryptography as it's more reliable
apt-get install -y python3-cryptography
# Use pip for the modern GUI toolkit
pip3 install customtkinter

echo "--- Installation Complete ---"
echo "All dependencies should now be installed."
