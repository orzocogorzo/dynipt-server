#! /usr/bin/env bash

sudo apt install -y sudo iptables python3 python3-venv git nginx
sudo useradd -M -s /usr/sbin/nologin dynipt

read -p "Set dynipt user password: " dynipt_pwd
(echo $dynipt_pwd, echo $dynipt_pwd) | sudo passwd dynipt
sed -i "s/DYNIPT_PWD=.*/DYNIPT_PWD=$dynipt_pwd/" .env
sudo usemod -aG sudo dynipt
sudo git clone https://github.com/orzocogorzo/dyniptables.git /opt/dyniptables
sudo chown -R dynipt: /opt/dyniptables

cd /opt/dyniptables
sudo -u dynipt python3 -m venv .venv
sudo -u dynipt .venv/bin/python -m pip install -r requirements.txt

sudo iptables -t filter -A FORWARD -p tcp -s $(ip a) --dport 8008 -j ACCEPT

sudo cp snippets/nginx.conf /etc/nginx/conf.d/dyniptables.conf
sudo cp snippets/systemd.service /etc/systemd/system/dyniptables.service

sudo nginx -s reload
sudo systemctl enable dyniptables
sudo systemctl start dyniptables
