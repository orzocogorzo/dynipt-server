#! /bin/bash

DIR=/opt/dynipt-server

# System requirements
sudo apt update
sudo apt install -y sudo iptables python3 python3-venv git nginx curl

# User creation
sudo useradd -M -s /usr/sbin/nologin dynipt
read -p "Set dynipt user password: " DYNIPT_PWD
echo -e "$DYNIPT_PWD\n$DYNIPT_PWD" | sudo passwd dynipt
sudo usermod -aG sudo dynipt

# Package download
sudo git clone https://github.com/orzocogorzo/dynipt-server.git $DIR
sudo chown -R dynipt: $DIR

# Setup config
HOST_PUBLIC_IP=$(curl ip.yunohost.org)
sudo -u dynipt sed -i "s/DYNIPT_HOST_IP=.*/DYNIPT_HOST_IP=$HOST_PUBLIC_IP/" $DIR/.env
sudo -u dynipt sed -i "s/DYNIPT_PWD=.*/DYNIPT_PWD=$DYNIPT_PWD/" $DIR/.env

# Python requirements
cd $DIR
sudo -u dynipt python3 -m venv .venv
sudo -u dynipt .venv/bin/python -m pip install -r requirements.txt

# Open dyniptables port
sudo iptables -t filter -I FORWARD -p tcp -s $HOST_PUBLIC_IP --dport 8000 -j ACCEPT

# System configuration
sudo cp snippets/nginx.conf /etc/nginx/conf.d/dynipt-server.conf
sudo rm /etc/nginx/sites-enabled/default
sudo cp snippets/systemd.service /etc/systemd/system/dynipt-server.service
sudo systemctl daemon-reload

# Service start
sudo nginx -s reload
sudo systemctl enable dyniptables
sudo systemctl start dyniptables

echo "DynIptables is installed and running!"
echo
.venv/bin/python app.py token
