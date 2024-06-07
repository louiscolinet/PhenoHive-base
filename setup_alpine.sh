#!/bin/bash
# Setup script for the PhenoHive project
# This script installs the necessary packages and enables the SPI interface on the Raspberry Pi
# It also sets up the PhenoHive service to run on boot
# It is intended to be run on a fresh install of Alpine Linux

# Color codes for the outputs
ERROR='\033[0;31m'
WARNING='\033[1;33m'
INFO='\033[0;36m'
WHITE='\033[0m'

# Run some checks before starting the setup
# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo -e "${ERROR}[ERROR] - Please run as root: sudo bash setup.sh${WHITE}"
  exit
fi

# Check if bash is being used
if [ -z "$BASH" ]; then
    echo -e "${ERROR}[ERROR] - Please run the script using bash: bash setup.sh${WHITE}"
    exit
fi

# Check if the script is being run on a Alpine-based system
if [ ! -f /etc/alpine-release ]; then
    echo -e "${ERROR}[ERROR] - This script is intended to run on a Alpine-based system.${WHITE}"
    exit
fi

# Check if 'git' is installed, if not, install it
if ! command -v git &> /dev/null
then
    echo -e "${WARNING}[WARNING] - git could not be found. Installing git...${WHITE}"
    apk add git >/dev/null2>&1
fi

# Check if 'python3' is installed, if not, install it
if ! command -v python3 &> /dev/null
then
    echo -e "${WARNING}[WARNING] - python3 could not be found. Installing python3...${WHITE}"
    apk add python3 >/dev/null2>&1
fi

# Check if 'pip' is installed, if not, install it
if ! command -v pip &> /dev/null
then
    echo -e "${WARNING}[WARNING] - pip could not be found. Installing pip...${WHITE}"
    apk add py3-pip python3-dev >/dev/null2>&1
    pip3 install --upgrade pip setuptools wheel >/dev/null2>&1
fi

# Start the setup
echo -e "${INFO}[INFO] - Installing necessary packages...${WHITE}"
# Install the necessary packages
apk update >/dev/null2>&1
# Install gcc and related packages
apk add linux-headers gcc build-base alpine-sdk openblas-dev spi-tools musl-dev py3-smbus py3-pillow #>/dev/null2>&1
# apk add gcc build-base build-essential libatlas-base-dev spi-tools musl-dev python-smbus python-pil

# Install the necessary Python packages
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
cd Python_ST7735 || echo -e "${ERROR}[ERROR] - Could not find the Python_ST7735 directory.${WHITE}"; exit
python3 setup.py install
cd ..; sudo rm -rf Python_ST7735
echo -e "${INFO}Packages installed successfully.${WHITE}"

echo -e "${INFO}Enabling SPI interface...${WHITE}"
# Enable the SPI interface
echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
echo -e "${INFO}SPI interface enabled successfully.${WHITE}"

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
echo -e "${INFO}[INFO] - PhenoHive service setup is not yet implemented.${WHITE}"

# Setup complete, reboot the Raspberry Pi
echo -e "${INFO}[INFO] - Setup complete. Push any key to reboot the Raspberry Pi.${WHITE}"
read -n 1 -s -r -p ""
# sudo reboot
