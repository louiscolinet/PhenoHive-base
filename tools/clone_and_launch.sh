#!/bin/bash
# This script is meant to be downloaded by the DietPi installer and run on a fresh install of DietPi (on first boot)
# It clones the PhenoHive repository and runs the setup script



# Check if the script is being run as root
if [ "$EUID" -ne 0 ]
  then echo -e "$(date) - Error: this script mus be run as root: sudo bash setup.sh" >&2
  exit 1
fi

# Check if git is installed
if ! command -v git &> /dev/null
then
    echo "$(date) - git could not be found. Installing git..."
    apt-get -y install git || { echo "$(date) - Error: failed to install git. Exiting" >&2; exit 1; }
fi

# Clone the PhenoHive repository and launch the setup script
git clone https://github.com/Oldgram/PhenoHive.git /root/PhenoHive
cd /root/PhenoHive || {
  echo "$(date) - Error: could not find PhenoHive directory. Exiting" >&2;
  exit 1;
}

if bash setup.sh; then
    echo "$(date) - Setup complete."
else
    echo "$(date) - Error: setup failed. Exiting." >&2
    exit 1
fi
