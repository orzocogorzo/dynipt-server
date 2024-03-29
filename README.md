# DynIPt server

Dynamic binding of IPs with [iptables](http://iptables.org/) as reverse proxy
to expose your LAN network.

## Description

Tiny solution to setup a VPS as a gateway to your local network. Like a dyndns
service but running at the level of the network/transport OSI layers.
This is an alternative solution to your home stations requirements for static
ip address without the need for a dynamic dns service and with capability
to work on top of IP address directly, without any domain name translations.

## How it works?

The package has two pieces, a [flask](https://flask.palletsprojects.com/en/2.2.x/)
microservice listening on an unofficial http port, like 8080, in charge of receiving,
via http, your local network public ip and update the VPS iptables rules. The other
piece of the puzzle is a crontab that triggers a http request with [curl](https://curl.se/)
every 5 minuts from some terminal in your LAN network.

## Installation

### On your VPS

To install **DynIPt server** on your VPS run:

```bash
curl -s https://raw.githubusercontent.com/orzocogorzo/dynipt-server/main/sh/install.sh > dynipt-install && bash ./dynipt-install
```

Once installed, to get your authorization token, run:

```bash
/opt/dynipt-server/.venv/bin/python app.py token
```

### On your local machine

On your LAN terminal, you will need **curl**, or other command line http client,
like **wget**, to perform http requests to your VPS and a **cron** daemon running.
Edit your crontab with `crontab -e` and copy the content of the [`snippets/crontab.txt`](https://github.com/orzocogorzo/dynipt-server/blob/main/snippets/crontab.txt)
replacing `*.*.*.*` with your server public ip adress and the `Authorization: *******`
with your token.

### Manual installation

If you need some customization on your installation, or you want to install **DynIPt server**
into a non-debian based OS, follow the next steps and modify

#### System requirements

```bash
# On the VPS
sudo apt install -y sudo iptables python3 python3-venv git
```

#### System user and directory

The recomended way to install the service is creating a dedicated user to run the
process and grant access to it to the service directory. This user will require
sudo privileges to interact with iptables.

```bash
# Create a dedicated user without login
sudo useradd -M -s /usr/sbin/nologin dynipt

# Setup the new user password. Remember it!
sudo passwd dynipt

# Add the new user to the sudo group
sudo usermod -aG sudo dynipt

# Clone the git repository
sudo git clone https://github.com/orzocogorzo/dynipt-server.git /opt/dynipt-server

# Grant ownership to the new user
sudo chown -R dynipt: /opt/dynipt-server
```

#### Python

Once you have the system requirements installed, next step is to install python requirements.

```bash
cd /opt/dynipt-server
sudo -u dynipt python3 -m venv .venv
sudo -u dynipt .venv/bin/python -m pip install -r requirements.txt
```

#### Open ports

In case you have a firewall, like **ufw**, or **iptables** configured to drop packets
as default policy, you will need to open port 8000 where nginx will be listening,
or port 8080 in case you want to expose flask without a front server. To achive
this, run the following command:

```bash
sudo iptables --table filter -A FORWARD -p tcp -s {your_vps_ip} --dport 8000 -j ACCEPT
```

## Config

The configuration of your instance is placed on the `.env` file placed on the root
directory of the package, next to the `app.py` file.

### Options

```bash
# The static IP of your VPS machine.
DYNIPT_HOST_IP=x.x.x.x

# A comma separated values list with the ports to forward
DYNIPT_PORTS=80,443

# A comma separated values list with the protocols to forward
DYNIPT_PROTOCOLS=tcp,udp

# Expose flask microservice behind a frontend server, like nginx, or respond from
# flask to remote requests directly.
# Flask server is intended for use only during local development. It is not designed
# to be particularly secure, stable, or efficient.
DYNIPT_FRONT_SERVER=true

# Dynipt user password
DYNIPT_PWD=******
```

## Start up the service

### With shell scripts

```bash
# Start the service with
sudo -u dynipt ./shell/start.sh

# Stop the service with
sudo -u dynipt ./shell/stop.sh
```

### With systemd

Another way to start/stop the service is as a systemd service. You can find an
service definition example on [`snippets/systemd.service`](https://github.com/orzocogorzo/dynipt-server/blob/main/snippets/systemd.service).
Edit the file to fit to your environment and move and rename it as `/etc/systemd/system/dynipt-server.service`.
After that, run

```bash
# Install the systemd package
sudo apt install -y systemd

# Enable automatic boot time starts
sudo systemctl enable dynipt-server

# Disable automatic boot time starts
sudo systemctl disable dynipt-server

# Manually start the service
sudo systemctl start dynipt-server

# Manually stop the service
sudo systemctl stop dynipt-server
```

## Front Server

Is recomended to expose the flask microservice behind a front service acting like
a reverse proxy to your local ports. I use [nginx](https://nginx.org/en/) on my
installation and you can find a reverse proxy configuration on the [`snippets/nginx.conf`](https://github.com/orzocogorzo/dynipt-server/blob/main/snippets/nginx.conf)
file. To get nginx running on your VPS as a front server install it with
`sudo apt install -y nginx` and move and rename the configuration to
`/etc/nginx/cond.d/dynipt-server.conf`. Then run `sudo nginx -s reload` to load the
new configuration.

For development or debugging pruposes, you may want to expose the python process
directly to the network. Then, update your `.env` file and set the _DYNIPT_FRONT_SERVER_
to `false` and start your service as always. Rember to switch to local exposure
behavior when you were finished.

## Bidirectional Proxy

Suppose you have an email service on your local machine, or perhaps an xmpp server.
In that case, you will need your outgoing communications to reach the internet
through your VPS to be bound to your public IP. In that case, you need your VPS
to work as a proxy and a reverse proxy at the same time. If this is your case, I
recommend you to use, at the same time as DynIPt server, [DynIPt client](https://github.com/orzocogorzo/dynipt-client)
on your local machine to easily route your packets through the VPS.
