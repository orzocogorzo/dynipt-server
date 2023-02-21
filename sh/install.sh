#! /bin/bash

DIR=/opt/dynipt-server

# System requirements
echo "Install system requirements..."
sudo apt -qq update > /dev/null 2>&1
sudo apt install -qqy sudo iptables python3 python3-venv git nginx curl  > /dev/null 2>&1
echo "System requirements installeds"
echo

# Package download
echo "Get source code..."
sudo git clone -q https://github.com/orzocogorzo/dynipt-server.git $DIR
echo "Source code placed on $DIR"
echo

# User creation
echo "Create system user 'dynipt'..."
sudo useradd -d $DIR -s /usr/sbin/nologin dynipt > /dev/null
sudo usermod -aG sudo dynipt > /dev/null
sudo chown -R dynipt: $DIR > /dev/null
DYNIPT_PWD=$(date +%s | sha256sum | base64 | head -c 32; echo)
echo -e "$DYNIPT_PWD\n$DYNIPT_PWD" | sudo passwd dynipt > /dev/null
echo "'dynipt' user created"
echo

# Setup config
echo "Configuring dynpt-server service"
HOST_PUBLIC_IP=$(curl ip.yunohost.org)
sudo -u dynipt sed -i "s/DYNIPT_HOST_IP=.*/DYNIPT_HOST_IP=$HOST_PUBLIC_IP/" $DIR/.env > /dev/null
sudo -u dynipt sed -i "s/DYNIPT_PWD=.*/DYNIPT_PWD=$DYNIPT_PWD/" $DIR/.env > /dev/null
sudo chmod 600 $DIR/.env > /dev/null
echo "Configuration done"
echo

# Open dynipt server port
echo "Opening ports on iptables..."
sudo iptables -t filter -I FORWARD -p tcp -s $HOST_PUBLIC_IP --dport 8000 -j ACCEPT > /dev/null
echo "Ports openeds"
echo

echo "Configuring dynipt-client systemd service..."
sudo cp $DIR/snippets/systemd.service /etc/systemd/system/dynipt-server.service
sudo systemctl daemon-reload
echo "SystemD service created"
echo

# Python requirements
echo "Install python dependencies..."
cd $DIR
sudo -u dynipt python3 -m venv .venv
sudo -u dynipt .venv/bin/python -m pip install -r requirements.txt > /dev/null
echo "Python is ready"
echo

# Nginx configuration
echo "Configuring nginx..."
sudo cp snippets/nginx.conf /etc/nginx/conf.d/dynipt-server.conf
sudo rm /etc/nginx/sites-enabled/default
echo "Nginx is ready"
echo

# Service start
sudo nginx -s reload
sudo systemctl enable dynipt-server
sudo systemctl start dynipt-server

echo "DynIPt server is installed and running!"
echo

.venv/bin/python app.py token
