#!/bin/bash

# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo "Please run as root: sudo ./setup.sh"
  exit
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
{
sudo apt-get update;
progress 6;
sudo apt-get install libatlas-base-dev;
progress 12;
sudo pip install numpy==1.23.5;
progress 18;
sudo pip install opencv-python==4.6.0.66;
progress 24;
sudo pip install scipy==1.8.1;
progress 30;
sudo pip install scikit-image==0.19.3;
progress 36;
sudo pip install pandas==2.0.0;
progress 42;
sudo pip install statsmodels==0.13.5;
progress 48;
sudo pip install plantcv;
progress 54;
sudo pip install influxdb_client;
progress 60;
sudo pip install configparser;
progress 66;
sudo pip install hx711;
progress 72;

# Install the ST7735 library
sudo apt-get install build-essential python-dev python-smbus python-pip python-pil python-numpy;
progress 78;
sudo pip install RPi.GPIO Adafruit_GPIO;
progress 84;
git clone https://github.com/degzero/Python_ST7735.git;
cd Python_ST7735 || echo "Error: Could not find the Python_ST7735 directory"; exit;
sudo python setup.py install;
progress 90;
cd ..; rm -rf Python_ST7735;
sudo apt-get autoremove;
progress 100;
} >> /dev/null
echo "Packages installed successfully."

echo "Enabling SPI interface..."
# Enable the SPI interface
sudo raspi-config nonint do_spi 0
echo "SPI interface enabled."

echo "Setting up PhenoHive service..."
# Copy the service file to the systemd directory
sudo cp phenoHive.service /etc/systemd/system
sudo chmod 644 /etc/systemd/system/phenoHive.service
sudo chmode +x /home/pi/PhenoHive/main.py
# Reload the systemd manager configuration
sudo systemctl daemon-reload
# Enable the service
sudo systemctl enable phenoHive.service
echo "PhenoHive service set up successfully."

# Setup complete, reboot the Raspberry Pi
echo "Setup complete. Push any key to reboot the Raspberry Pi."
read -n 1 -s -r -p ""
sudo reboot
