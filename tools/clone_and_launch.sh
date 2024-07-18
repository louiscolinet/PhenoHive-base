#!/bin/bash
# This script is meant to be downloaded by the DietPi installer and run on a fresh install of DietPi (on first boot)
# It clones the PhenoHive repository and runs the setup script

# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo -e "Error: this script mus be run as root: sudo bash setup.sh" >&2
  exit 1
fi

# Check if git is installed
if ! command -v git &> /dev/null
then
    echo "git could not be found. Installing git..."
    apt-get -y install git || { echo "Error: failed to install git. Exiting" >&2; exit 1; }
fi

# Clone the PhenoHive repository and launch the setup script
git clone https://github.com/Oldgram/PhenoHive.git /home/pi/PhenoHive
cd /home/pi/PhenoHive || { echo "Error: could not find PhenoHive directory. Exiting" >&2; exit 1; }

if bash setup.sh; then
    echo "Setup complete. Rebooting..."
else
    echo "Error: setup failed. Exiting." >&2
    exit 1
fi

reboot
