#!/bin/bash
# Setup script for the PhenoHive project
# This script installs the necessary packages and enables the SPI interface on the Raspberry Pi
# It also sets up the PhenoHive service to run on boot
# It is intended to be run on a fresh install of Alpine Linux

# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo "Please run as root: sudo ./setup.sh"
  exit
fi

# Check if the script is being run on a Alpine-based system
if [ ! -f /etc/alpine-release ]; then
    echo "This script is intended to run on a Alpine-based system."
    exit
fi

# Check if 'pip' is installed, if not, install it
if ! command -v pip &> /dev/null
then
    echo "pip could not be found. Installing pip..."
    apk add py3-pip >> /dev/null 2>&1
fi

# Progress bar function
function progress {
    bar="##################################################"
    barlength=${#bar}
    n=$(($1*barlength/100))
    printf "\r[%-${barlength}s (%d%%)] " "${bar:0:n}" "$1"
}

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv >> /dev/null 2>&1
source venv/bin/activate >> /dev/null 2>&1
echo "Virtual environment created successfully."

echo "Installing necessary packages..."
# Install the necessary packages

progress 0
apk update >> /dev/null 2>&1
progress 6
apk add libatlas-base-dev >> /dev/null 2>&1
progress 12
apk add py3-numpy==1.25.2-r0 >> /dev/null 2>&1
progress 18
apk add py3-opencv-python==4.8.1-r0 >> /dev/null 2>&1
progress 24
pip install scipy==1.8.1 >> /dev/null 2>&1
progress 30
pip install scikit-image==0.19.3 >> /dev/null 2>&1
progress 36
pip install pandas==2.0.0 >> /dev/null 2>&1
progress 42
pip install statsmodels==0.13.5 >> /dev/null 2>&1
progress 48
pip install plantcv >> /dev/null 2>&1
progress 54
pip install influxdb_client >> /dev/null 2>&1
progress 60
pip install configparser >> /dev/null 2>&1
progress 66
pip install hx711 >> /dev/null 2>&1
progress 72

# Install gcc and related packages
apk add gcc build-base spi-tools musl-dev >> /dev/null 2>&1
# Add testing repository
echo "http://dl-cdn.alpinelinux.org/alpine/edge/testing" | sudo tee -a /etc/apk/repositories
# Install py3-spidev
apk add py3-spidev >> /dev/null 2>&1
progress 78

# Install the ST7735 library
apk add build-essential python-dev python-smbus python-pil >> /dev/null 2>&1
progress 84
pip install RPi.GPIO Adafruit_GPIO >> /dev/null 2>&1
progress 90
git clone https://github.com/degzero/Python_ST7735.git >> /dev/null 2>&1
cd Python_ST7735 || echo "Error: Could not find the Python_ST7735 directory"; exit
python setup.py install >> /dev/null 2>&1
progress 96
cd ..; sudo rm -rf Python_ST7735 >> /dev/null 2>&1
progress 100
echo "Packages installed successfully."

echo "Enabling SPI interface..."
# Enable the SPI interface
echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
echo "SPI interface enabled successfully."

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
echo "Warning: PhenoHive service setup is not yet implemented."

# Setup complete, reboot the Raspberry Pi
echo "Setup complete. Push any key to reboot the Raspberry Pi."
read -n 1 -s -r -p ""
sudo reboot
