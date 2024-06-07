#!/bin/bash
# Setup script for the PhenoHive project
# This script installs the necessary packages and enables the SPI interface on the Raspberry Pi
# It also sets up the PhenoHive service to run on boot
# It is intended to be run on a fresh install of Alpine Linux
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo "${RED}Please run as root: sudo ./setup.sh"
  exit
fi

# Check if the script is being run on a Alpine-based system
if [ ! -f /etc/alpine-release ]; then
    echo "${RED}This script is intended to run on a Alpine-based system."
    exit
fi

# Check if 'git' is installed, if not, install it
if ! command -v git &> /dev/null
then
    echo "${RED}git could not be found. Installing git..."
    apk add git &> /dev/null
fi

# Check if 'python3' is installed, if not, install it
if ! command -v python3 &> /dev/null
then
    echo "${YELLOW}python3 could not be found. Installing python3..."
    apk add python3 &> /dev/null
fi

# Check if 'pip' is installed, if not, install it
if ! command -v pip &> /dev/null
then
    echo "${YELLOW}pip could not be found. Installing pip..."
    apk add py3-pip python3-dev
    pip3 install --upgrade pip setuptools wheel
fi

echo "${YELLOW}Installing necessary packages..."
# Install the necessary packages
apk update &> /dev/null
# Install gcc and related packages
apk add gcc build-base alpine-sdk py3-smbus spi-tools musl-dev py3-pillow
# apk add gcc build-base build-essential libatlas-base-dev spi-tools musl-dev python-smbus python-pil
pip3 install numpy
pip3 install opencv-python
pip3 install scipy
pip3 install scikit-image
pip3 install pandas
pip3 install statsmodels
pip3 install plantcv
pip3 install influxdb_client
pip3 install configparser
pip3 install hx711

# Add testing repository
echo "http://dl-cdn.alpinelinux.org/alpine/edge/testing" | sudo tee -a /etc/apk/repositories
# Install spidev
pip3 install spidev

# Install the ST7735 library
pip3 install RPi.GPIO Adafruit_GPIO
git clone https://github.com/degzero/Python_ST7735.git
cd Python_ST7735 || echo "SETUP - Error: Could not find the Python_ST7735 directory"; exit
python3 setup.py install
cd ..; sudo rm -rf Python_ST7735
echo "SETUP - Packages installed successfully."

echo "SETUP - Enabling SPI interface..."
# Enable the SPI interface
echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
echo "SETUP - SPI interface enabled successfully."

# echo "Setting up PhenoHive service..."
# # Copy the service file to the systemd directory
# sudo cp phenoHive.service /etc/systemd/system
# sudo chmod 644 /etc/systemd/system/phenoHive.service
# sudo chmode +x /home/pi/PhenoHive/main.py
# # Reload the systemd manager configuration
# sudo systemctl daemon-reload
# # Enable the service
# sudo systemctl enable phenoHive.service
# echo "PhenoHive service set up successfully."
echo "SETUP - Warning: PhenoHive service setup is not yet implemented."

# Setup complete, reboot the Raspberry Pi
echo "SETUP - Setup complete. Push any key to reboot the Raspberry Pi."
read -n 1 -s -r -p ""
# sudo reboot
