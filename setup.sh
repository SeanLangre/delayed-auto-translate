#!/bin/bash
# Quick setup script for live-translate

set -e

echo "=== Live Audio Translation Setup ==="
echo

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "Warning: This script is designed for Linux with PulseAudio"
fi

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pyaudio portaudio19-dev

# Activate virtual environment
echo
echo "Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Download Vosk model
echo
echo "Downloading Vosk speech recognition model..."
python setup_model.py

echo
echo "=== Setup Complete! ==="
echo
echo "To run the live translator:"
echo "  source venv/bin/activate"
echo "  python live_translate.py"
echo
echo "See README.md for more information."
