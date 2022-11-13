# dyniptables

Dynamic binding of IPs with [iptables](http://iptables.org/) as reverse proxy to expose your LAN network.  

## Description

Tiny solution to setup a VPS as a gateway to your local network. Like a dyndns service but running at the level of the network/transport OSI layers.
This is an alternative solution to your home stations requirements of static ip address without the need of a dynamic dns service and with capability
to work on top of IP address directly, without any domain name translations.

## How it works?

The package has two pieces, a [flask](https://flask.palletsprojects.com/en/2.2.x/) microservice listening on an unofficial http port, like 8080,
responsible of receiving, via http, your local network public ip and update the VPS iptables rules. The other piece of the puzzle is a crontab
that triggers a http request with [curl](https://curl.se/) each 5 minuts from some terminal in your LAN network.

## Installation
On your VPS you will need to have installed `iptables` and `python3` packages with the `sudo` package and the `python3-venv` module.

On your LAN terminal, you will need `curl`, or other command line http client to perform http requests to your VPS.

### System requirements

```bash
# On the VPS
sudo apt install -y sudo iptables python3 python3-venv git
```

```bash
# On your local machine
sudo apt install -y curl
```

### System user and directory

The recomended way to install the service is creating a dedicated user to run the process and grant access to it to the service directory.
This user will require sudo privileges to interact with iptables.

```bash
# Create a dedicated user without login
sudo useradd -M -s /usr/sbin/nologin dynipt
# Setup the new user password. Remember it!
sudo passwd dynipt
# Add the new user to the sudo group
sudo usermod -aG sudo dynipt
# Clone the git repository
sudo git clone https://github.com/orzocogorzo/dyniptables.git /opt/dyniptables
# Grant ownership to the new user
sudo chown -R dynipt: /opt/dyniptables
```

### Python

Once you have the system requirements installed, next step is to install python requirements.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Config

The configuration of your instance is placed on the `.env` file placed on the root directory of the package, next to the `app.py` file.

### Options

```bash
# The static IP of your VPS machine.
DYNIPT_HOST_IP=x.x.x.x
# A comma separated values list with the ports to forward
DYNIPT_PORTS=80,443
# A comma separated values list with the protocols to forward
DYNIPT_PROTOCOLS=tcp,udp
# Expose flask microservice behind a frontend server, like nginx, or respond from flask to remote requests directly.
# Flask server is intended for use only during local development. It is not designed to be particularly
# secure, stable, or efficient.
DYNIPT_FRONT_SERVER=true
# Your dedicated user password
DYNIPT_PWD=******
```

## Start up the service

### With shell scripts

```bash
# Start the service with
sudo ./shell/start.sh

# Stop the service with
sudo ./shell/stop.sh
```

### With systemd

Another way to start/stop the service is as a systemd service. You can find an service definition example on `snippets/dyniptables.service`.
Edit the file to fit to your environment and place it on the `/etc/systemd/system` directory. After that, run

```bash
# Install the package
sudo apt install -y systemd

# To enable automatic boot time starts
sudo systemctl enable dyniptables

# To disable automatic boot time starts
sudo systemctl disable dyniptables

# To manually start the service
sudo systemctl start dyniptables

# To manually stop the service
sudo systemctl stop dyniptables
```

## Front Server

Is recomended to expose the flask microservice behind a front service acting like a reverse proxy to your local ports. I use [nginx](https://nginx.org/en/)
on my installation and you can find a reverse proxy configuration on the `snippets` subdirectory. To get nginx running on your VPS as a front server 
install it with `sudo apt install -y nginx` and place the configuration file inside `/etc/nginx/cond.d` directory. Then run `sudo nginx -s reload` to
load the new configuration.
