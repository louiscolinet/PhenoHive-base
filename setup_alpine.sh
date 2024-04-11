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

# Check if 'sudo' is installed
if ! command -v sudo &> /dev/null
then
    echo "sudo could not be found. Please install sudo and try again: apk add sudo"
    exit
fi

# Check if 'pip' is installed, if not, install it
if ! command -v pip &> /dev/null
then
    echo "pip could not be found. Installing pip..."
    sudo apk add py3-pip >> /dev/null 2>&1
fi

# Progress bar function
function progress {
    bar="##################################################"
    barlength=${#bar}
    n=$(($1*barlength/100))
    printf "\r[%-${barlength}s (%d%%)] " "${bar:0:n}" "$1"
}

echo "Installing necessary packages..."
# Install the necessary packages

progress 0
sudo apk update >> /dev/null 2>&1
progress 6
sudo apk add libatlas-base-dev >> /dev/null 2>&1
progress 12
sudo pip install numpy==1.23.5 >> /dev/null 2>&1
progress 18
sudo pip install opencv-python==4.6.0.66 >> /dev/null 2>&1
progress 24
sudo pip install scipy==1.8.1 >> /dev/null 2>&1
progress 30
sudo pip install scikit-image==0.19.3 >> /dev/null 2>&1
progress 36
sudo pip install pandas==2.0.0 >> /dev/null 2>&1
progress 42
sudo pip install statsmodels==0.13.5 >> /dev/null 2>&1
progress 48
sudo pip install plantcv >> /dev/null 2>&1
progress 54
sudo pip install influxdb_client >> /dev/null 2>&1
progress 60
sudo pip install configparser >> /dev/null 2>&1
progress 66
sudo pip install hx711 >> /dev/null 2>&1
progress 72

# Install the ST7735 library
sudo apk add build-essential python-dev python-smbus python-pip python-pil python-numpy  >> /dev/null 2>&1
progress 78
sudo pip install RPi.GPIO Adafruit_GPIO >> /dev/null 2>&1
progress 84
git clone https://github.com/degzero/Python_ST7735.git >> /dev/null 2>&1
cd Python_ST7735 || echo "Error: Could not find the Python_ST7735 directory"; exit
sudo python setup.py install >> /dev/null 2>&1
progress 90
cd ..; rm -rf Python_ST7735 >> /dev/null 2>&1
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
