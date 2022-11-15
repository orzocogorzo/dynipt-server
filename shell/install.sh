#! /usr/bin/env bash

cd $(dirname $0) && cd ..
if ! [ -f .env ]; then
    echo "You should place a .env file in the root directory of the repository"
    exit 1
fi

source .env

if [ -z "$DYNIPT_HOST_IP" ]; then
    echo "You have to set your host ip in the .env file"
    exit 1
fi

sudo apt update
sudo apt install -y sudo iptables python3 python3-venv git nginx
sudo useradd -M -s /usr/sbin/nologin dynipt

if [ -z "$DYNIPT_PWD" ]; then
    read -p "Set dynipt user password: " DYNIPT_PWD
    (echo $DYNIPT_PWD, echo $DYNIPT_PWD) | sudo passwd dynipt
    sed -i "s/DYNIPT_PWD=.*/DYNIPT_PWD=$DYNIPT_PWD/" .env
fi

sudo usemod -aG sudo dynipt
sudo git clone https://github.com/orzocogorzo/dyniptables.git /opt/dyniptables
sudo chown -R dynipt: /opt/dyniptables

cd /opt/dyniptables
sudo -u dynipt python3 -m venv .venv
sudo -u dynipt .venv/bin/python -m pip install -r requirements.txt

sudo iptables -t filter -A FORWARD -p tcp -s $DYNIPT_HOST_IP --dport 8008 -j ACCEPT

sudo cp snippets/nginx.conf /etc/nginx/conf.d/dyniptables.conf
sudo cp snippets/systemd.service /etc/systemd/system/dyniptables.service

sudo nginx -s reload
sudo systemctl enable dyniptables
sudo systemctl start dyniptables
