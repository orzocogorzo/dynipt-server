#! /usr/bin/env bash

# System requirements
sudo apt update
sudo apt install -y sudo iptables python3 python3-venv git nginx curl

# User creation
sudo useradd -M -s /usr/sbin/nologin dynipt
read -p "Set dynipt user password: " DYNIPT_PWD
echo -e "$DYNIPT_PWD\n$DYNIPT_PWD" | sudo passwd dynipt
sudo usermod -aG sudo dynipt

# Package download
sudo git clone https://github.com/orzocogorzo/dyniptables.git /opt/dyniptables
sudo chown -R dynipt: /opt/dyniptables

# Setup config
HOST_PUBLIC_IP=$(curl ip.yunohost.org)
sudo -u dynipt sed -i "s/DYNIPT_HOST_IP=.*/DYNIPT_HOST_IP=$HOST_PUBLIC_IP/" /opt/dyniptables/.env
sudo -u dynipt sed -i "s/DYNIPT_PWD=.*/DYNIPT_PWD=$DYNIPT_PWD/" /opt/dyniptables/.env

# Python requirements
cd /opt/dyniptables
sudo -u dynipt python3 -m venv .venv
sudo -u dynipt .venv/bin/python -m pip install -r requirements.txt

# Open dyniptables port
sudo iptables -t filter -I FORWARD -p tcp -s $HOST_PUBLIC_IP --dport 8008 -j ACCEPT

# System configuration
sudo cp snippets/nginx.conf /etc/nginx/conf.d/dyniptables.conf
sudo cp snippets/systemd.service /etc/systemd/system/dyniptables.service

# Service start
sudo nginx -s reload
sudo systemctl enable dyniptables
sudo systemctl start dyniptables
