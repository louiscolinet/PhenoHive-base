#!/bin/bash
# Setup script for the PhenoHive project
# This script installs the necessary packages and enables the SPI interface on the Raspberry Pi
# It also sets up the PhenoHive service to run on boot
# It is intended to be run on a fresh install of Alpine Linux

# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo "SETUP - Please run as root: sudo ./setup.sh"
  exit
fi

# Check if the script is being run on a Alpine-based system
if [ ! -f /etc/alpine-release ]; then
    echo "SETUP - This script is intended to run on a Alpine-based system."
    exit
fi

# Check if 'pip' is installed, if not, install it
if ! command -v pip &> /dev/null
then
    echo "SETUP - pip could not be found. Installing pip..."
    apk add py3-pip >> /dev/null 2>&1
fi

# Create virtual environment
echo "SETUP - Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "SETUP - Virtual environment created successfully."

echo "SETUP - Installing necessary packages..."
# Install the necessary packages

apk update
# Install gcc and related packages
apk add libatlas-base-dev gcc build-base spi-tools musl-dev build-essential python-dev python-smbus python-pil
apk add py3-numpy==1.25.2-r0
apk add py3-opencv-python==4.8.1-r0
pip install scipy==1.8.1
pip install scikit-image==0.19.3
pip install pandas==2.0.0
pip install statsmodels==0.13.5
pip install plantcv
pip install influxdb_client
pip install configparser
pip install hx711

# Add testing repository
echo "http://dl-cdn.alpinelinux.org/alpine/edge/testing" | sudo tee -a /etc/apk/repositories
# Install py3-spidev
apk add py3-spidev

# Install the ST7735 library
pip install RPi.GPIO Adafruit_GPIO
git clone https://github.com/degzero/Python_ST7735.git
cd Python_ST7735 || echo "SETUP - Error: Could not find the Python_ST7735 directory"; exit
python setup.py install
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
