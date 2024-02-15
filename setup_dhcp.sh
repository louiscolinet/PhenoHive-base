#!/usr/bin/bash

# Check if the script is being run as root
if [[ "${UID}" -ne 0 ]]
then
  echo "Please run this script as root" >&2
  exit 1
fi

# Check arguments
if [[ "${#}" -ne 1 ]]
then
  echo "Usage: ${0} <station_id> <password>" >&2
  exit 1
fi

# Update the system
echo "Updating the system"
sudo apt-get update
sudo apt-get dist-upgrade

# Install the necessary packages
echo "Installing hostapd and dnsmasq packages"
sudo apt-get install hostapd dnsmasq

# Stop the services
echo "Stopping the services"
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

# Backup the configuration files
echo "Backing up the configuration files"
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
sudo mv /etc/hostapd/hostapd.conf /etc/hostapd/hostapd.conf.orig
sudo mv /etc/default/hostapd /etc/default/hostapd.orig

# Edit the dnsmasq configuration file
echo "Editing the dnsmasq configuration file"
sudo cat > /etc/dnsmasq.conf <<EOF
interface=wlan0
dhcp-range=192.168.4.2,.192.168.4.100,255.255.255.0,24h
EOF

# Edit the hostapd configuration file
echo "Editing the hostapd configuration file"
sudo cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=PhenoHiveStation${1}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${2}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Edit the hostapd default file
echo "Editing the hostapd default file"
sudo sed -i 's/#DAEMON_CONF=""/DAEMON_CONF="\/etc\/hostapd\/hostapd.conf"/' /etc/default/hostapd

# Configure the network interfaces
echo "Configuring the network interfaces"
sudo cat > /etc/dhcpcd.conf <<EOF
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF

# Start the services
echo "Starting the services"
sudo service dhcpcd restart
sudo service hostapd start
sudo sytemctl enable hostapd$

# Enable routing
echo "Enabling routing"
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"
sudo apt-get install iptables-persistent

# Reboot the system
echo "Rebooting the system, press any key to continue"
read -n 1 -s
sudo reboot
