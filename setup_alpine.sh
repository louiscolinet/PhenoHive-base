#!/bin/bash
# Setup script for the PhenoHive project
# This script installs the necessary packages and enables the SPI interface on the Raspberry Pi
# It also sets up the PhenoHive service to run on boot
# It is intended to be run on a fresh install of Alpine Linux running on a Raspberry Pi Zero W

# Color codes for the outputs
ERROR='\033[0;31m'
WARNING='\033[1;33m'
INFO='\033[0;36m'
WHITE='\033[0m'

echo -e "${INFO}[INFO] - PhenoHive Setup Script.\n" \
        "\t This script installs the necessary packages and enables the SPI interface.\n" \
        "\t It also sets up the PhenoHive service to run on boot.\n" \
        "\t It is intended to be run on a fresh install of Alpine Linux running on a Raspberry Pi Zero W.\n" \
        "\t Please ensure that the Raspberry Pi is connected to the internet before running this script.\n" \
        "\t Press any key to continue...${WHITE}"
read -n 1 -s -r -p ""

# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo -e "${ERROR}[ERROR] - Please run as root: sudo bash setup.sh${WHITE}"
  exit
fi

# Check if the script is being run on a Alpine-based system
if [ ! -f /etc/alpine-release ]; then
    echo -e "${ERROR}[ERROR] - This script is intended to run on a Alpine-based system.${WHITE}"
    exit
fi

# Check if bash is being used
if [ -z "$BASH" ]; then
    echo -e "${ERROR}[ERROR] - Please run the script using bash: bash setup.sh${WHITE}"
    exit
fi

# Run some checks before starting the setup
echo -e "${INFO}[INFO] - Running pre-setup checks...${WHITE}"

# Change repository to 3.19
echo "http://dl-cdn.alpinelinux.org/alpine/v3.19/main" | sudo tee /etc/apk/repositories >/dev/null2>&1
echo "http://dl-cdn.alpinelinux.org/alpine/v3.19/community" | sudo tee -a /etc/apk/repositories >/dev/null2>&1
# Add testing repository
echo "http://dl-cdn.alpinelinux.org/alpine/edge/testing" | sudo tee -a /etc/apk/repositories >/dev/null2>&1

# Ensure the package list is up to date
apk update >/dev/null2>&1
# Install ca-certificates
apk --no-cache add ca-certificates >/dev/null2>&1
# Install gcc and related packages
apk add linux-headers gcc build-base alpine-sdk 

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
    # We need python3.11 as python3.12 is not supported yet by opencv-python
    apk add python3==3.11.9-r0 >/dev/null2>&1
fi

# Check if 'pip' is installed, if not, install it
if ! command -v pip &> /dev/null
then
    echo -e "${WARNING}[WARNING] - pip could not be found. Installing pip...${WHITE}"
    apk add py3-pip >/dev/null2>&1
    python3 -m ensurepip --upgrade >/dev/null2>&1
    python3 -m pip install --upgrade wheel setuptools --break-system-packages --root-user-action=ignore >/dev/null2>&1
fi

# Start the setup
echo -e "${INFO}[INFO] - Installing necessary packages...${WHITE}"

# Install the necessary Alpine packages
apk add cargo openblas-dev spi-tools musl-dev python3-dev py3-smbus py3-pillow py3-numpy py3-opencv py3-scipy

# Install the necessary Python packages (note: --break-system-packages is used to avoid conflicts with the system packages)
#pip install opencv-python scipy scikit-image pandas statsmodels plantcv influxdb_client configparser hx711 spidev RPi.GPIO Adafruit_GPIO --break-system-packages --root-user-action=ignore
pip install scikit-image --break-system-packages --root-user-action=ignore
pip install pandas --break-system-packages --root-user-action=ignore
pip install statsmodels --break-system-packages --root-user-action=ignore
pip install plantcv --break-system-packages --root-user-action=ignore
pip install influxdb_client --break-system-packages --root-user-action=ignore
pip install configparser --break-system-packages --root-user-action=ignore
pip install hx711 --break-system-packages --root-user-action=ignore
pip install spidev --break-system-packages --root-user-action=ignore
pip install RPi.GPIO --break-system-packages --root-user-action=ignore
pip install Adafruit_GPIO --break-system-packages --root-user-action=ignore

# Disable git ssl verification
git config --global http.sslVerify false

# Install the ST7735 library
git clone https://github.com/degzero/Python_ST7735.git
cd Python_ST7735 || echo -e "${ERROR}[ERROR] - Could not find the Python_ST7735 directory.${WHITE}"
python3 setup.py install
cd ..; sudo rm -rf Python_ST7735
echo -e "${INFO}[INFO] - Packages installed successfully.${WHITE}"

echo -e "${INFO}[INFO] - Enabling SPI interface...${WHITE}"
# Enable the SPI interface
echo "dtparam=spi=on" | sudo tee -a /boot/config.txt

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
echo -e "${WARNING}[WARNING] - PhenoHive service setup is not yet implemented.${WHITE}"

# Setup complete, reboot the Raspberry Pi
echo -e "${INFO}[INFO] - Setup complete. Push any key to reboot the Raspberry Pi.${WHITE}"
read -n 1 -s -r -p ""
# sudo reboot
