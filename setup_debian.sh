#!/bin/bash
# Setup script for the PhenoHive project
# This script installs the necessary packages and enables the SPI interface on the Raspberry Pi
# It also sets up the PhenoHive service to run on boot
# It is intended to be run on a fresh install on a Debian Linux Distribution (Raspbian or DietPi)

# Color codes for the outputs
ERROR='\033[0;31m'
WARNING='\033[1;33m'
INFO='\033[0;36m'
WHITE='\033[0m'

echo -e "${INFO}[INFO] - PhenoHive Setup Script.\n" \
        "\t This script installs the necessary packages and enables the SPI interface.\n" \
        "\t It also sets up the PhenoHive service to run on boot.\n" \
        "\t It is intended to be run on a fresh install of a Debian Linux Distribution (DietPi or Raspbian) running on a Raspberry Pi Zero W.\n" \
        "\t Please ensure that the Raspberry Pi is connected to the internet before running this script.\n" \
        "\t Press any key to continue...${WHITE}"
read -n 1 -s -r -p ""

# Check that the device is connected to the internet
if ! ping -q -c 1 -W 1 google.com &> /dev/null
then
    echo -e "${ERROR}[ERROR] - Please ensure that the Raspberry Pi is connected to the internet before running this script.${WHITE}"
    exit
fi

# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo -e "${ERROR}[ERROR] - Please run as root: sudo bash setup.sh${WHITE}"
  exit
fi

echo -e "${INFO}[INFO] - Running pre-setup checks...${WHITE}"

# Remove apt compression to speed up the process
echo 'Acquire::GzipIndexes "false";' > /etc/apt/apt.conf.d/98dietpi-uncompressed
/boot/dietpi/func/dietpi-set_software apt-cache clean

# Ensure system is at the latest version
apt-get update  >/dev/null2>&1

# Check if the script is being run on a Debian-based system
if [ ! -f /etc/debian_version ]; then
    echo -e "${ERROR}[ERROR] - This script is intended to run on a Debian Linux Distribution.${WHITE}"
    exit
fi

# Check if 'git' is installed, if not, install it
if ! command -v git &> /dev/null
then
    echo -e "${WARNING}[WARNING] - git could not be found. Installing git...${WHITE}"
    apt-get -y install git >/dev/null2>&1
fi

# Check if 'python3' is installed, if not, install it
if ! command -v python3 &> /dev/null
then
    echo -e "${WARNING}[WARNING] - python3 could not be found. Installing python3...${WHITE}"
    # We need python3.11 as python3.12 is not supported yet by opencv-python
    apt-get -y install python3.11 >/dev/null2>&1
fi

# Check if 'pip' is installed, if not, install it
if ! command -v pip &> /dev/null
then
    echo -e "${WARNING}[WARNING] - pip could not be found. Installing pip...${WHITE}"
    apt-get -y install python3-pip >/dev/null2>&1
    python3 -m ensurepip --upgrade >/dev/null2>&1
    python3 -m pip install --upgrade wheel setuptools --break-system-packages --root-user-action=ignore --no-cache-dir >/dev/null2>&1
fi

echo -e "${INFO}[INFO] - Installing necessary packages...${WHITE}"

apt-get -y install build-essential #>> /dev/null 2>&1
apt-get -y install python-dev #>> /dev/null 2>&1
apt-get -y install python-smbus #>> /dev/null 2>&1
apt-get -y install libatlas-base-dev #>> /dev/null 2>&1

# Install the necessary packages
pip install numpy==1.23.5 --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install opencv-python==4.6.0.66 --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install scipy==1.8.1 --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install scikit-image==0.19.3 --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install pandas==2.0.0 --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install statictics --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install statsmodels==0.13.5 --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install plantcv --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install influxdb_client --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install configparser --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install hx711 --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install RPi.GPIO --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1
pip install Adafruit_GPIO --break-system-packages --root-user-action=ignore --no-cache-dir #>> /dev/null 2>&1

# Install the ST7735 library
git clone https://github.com/degzero/Python_ST7735.git >> /dev/null 2>&1
cd Python_ST7735 || echo -e "${ERROR}[ERROR] - Python_ST335 could not be installed: Could not find directory.${WHITE}"
python setup.py install >> /dev/null 2>&1

# Cleanup unnecessary packages and directory
cd ..; rm -rf Python_ST7735 #>> /dev/null 2>&1
apt-get autoremove #>> /dev/null 2>&1
echo -e "${INFO}[INFO] - Packages installed successfully.${WHITE}"

echo -e "${INFO}[INFO] - Enabling SPI interface...${WHITE}"
# Enable the SPI interface
raspi-config nonint do_spi 0
# echo "dtparam=spi=on" | sudo tee -a /boot/config.txt

echo -e "${INFO}[INFO] - Setting up PhenoHive service...${WHITE}"
# Copy the service file to the systemd directory
cp phenoHive.service /etc/systemd/system
chmod 644 /etc/systemd/system/phenoHive.service
chmode +x /home/pi/PhenoHive/main.py
# Reload the systemd manager configuration
systemctl daemon-reload
# Enable the service
systemctl enable phenoHive.service
echo -e "${INFO}PhenoHive service set up successfully.${WHITE}"

# Setup complete, reboot the Raspberry Pi
echo -e "${INFO}Setup complete. Push any key to reboot the Raspberry Pi.${WHITE}"
read -n 1 -s -r -p ""
#sudo reboot
