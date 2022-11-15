#! /usr/bin/env bash

sudo apt update
sudo apt install -y sudo iptables python3 python3-venv git nginx curl
sudo useradd -M -s /usr/sbin/nologin dynipt

HOST_PUBLIC_IP=$(curl https://ip.yunhost.org)

sudo usemod -aG sudo dynipt
sudo git clone https://github.com/orzocogorzo/dyniptables.git /opt/dyniptables
sudo chown -R dynipt: /opt/dyniptables

cd /opt/dyniptables
sudo -u dynipt python3 -m venv .venv
sudo -u dynipt .venv/bin/python -m pip install -r requirements.txt

sudo iptables -t filter -A FORWARD -p tcp -s $HOST_PUBLIC_IP --dport 8008 -j ACCEPT

sudo cp snippets/nginx.conf /etc/nginx/conf.d/dyniptables.conf
sudo cp snippets/systemd.service /etc/systemd/system/dyniptables.service

sudo nginx -s reload
sudo systemctl enable dyniptables
sudo systemctl start dyniptables
