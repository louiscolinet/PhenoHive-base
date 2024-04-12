#!/bin/bash
# Setup script for the PhenoHive project
# This script installs the necessary packages and enables the SPI interface on the Raspberry Pi
# It also sets up the PhenoHive service to run on boot
# It is intended to be run on a fresh install of Raspbian

# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo "Please run as root: sudo ./setup.sh"
  exit
fi

# Check if the script is being run on a Debian-based system
if [ ! -f /etc/debian_version ]; then
    echo "This script is intended to run on a Debian-based system."
    exit
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
apt-get update >> /dev/null 2>&1
progress 6
apt-get install libatlas-base-dev >> /dev/null 2>&1
progress 12
pip install numpy==1.23.5 >> /dev/null 2>&1
progress 18
pip install opencv-python==4.6.0.66 >> /dev/null 2>&1
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

# Install the ST7735 library
sudo apt-get install build-essential python-dev python-smbus python-pip python-pil python-numpy  >> /dev/null 2>&1
progress 78
pip install RPi.GPIO Adafruit_GPIO >> /dev/null 2>&1
progress 84
git clone https://github.com/degzero/Python_ST7735.git >> /dev/null 2>&1
cd Python_ST7735 || echo "Error: Could not find the Python_ST7735 directory"; exit
python setup.py install >> /dev/null 2>&1
progress 90
cd ..; rm -rf Python_ST7735 >> /dev/null 2>&1
apt-get autoremove >> /dev/null 2>&1
progress 100
echo "Packages installed successfully."

echo "Enabling SPI interface..."
# Enable the SPI interface
raspi-config nonint do_spi 0
echo "SPI interface enabled."

echo "Setting up PhenoHive service..."
# Copy the service file to the systemd directory
cp phenoHive.service /etc/systemd/system
chmod 644 /etc/systemd/system/phenoHive.service
chmode +x /home/pi/PhenoHive/main.py
# Reload the systemd manager configuration
systemctl daemon-reload
# Enable the service
systemctl enable phenoHive.service
echo "PhenoHive service set up successfully."

# Setup complete, reboot the Raspberry Pi
echo "Setup complete. Push any key to reboot the Raspberry Pi."
read -n 1 -s -r -p ""
sudo reboot
