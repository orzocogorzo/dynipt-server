from os import getenv
import re
from subprocess import Popen, PIPE
from pathlib import Path
from typing import Optional
from http.client import HTTPConnection, HTTPException

# VENDOR
from dotenv import load_dotenv
from flask import Flask, request, abort

load_dotenv()


app = Flask(__name__)


def get_state() -> tuple[str, str]:
    if not Path("var/state").is_file():
        Path("var/state").touch(mode=0o600)
        return ("", "")

    with open("var/state", "r") as f:
        return tuple(f.read().split(":"))


def set_state(host_ip, dest_ip: str) -> None:
    with open("var/state", "w") as f:
        f.write("%s:%s" % (host_ip, dest_ip))


def fetch_ip():
    conn = HTTPConnection("ip.yunhost.org")
    conn.request("GET", "/")
    res = conn.getresponse()
    if res.status == 200:
        return res.read().decode()
    else:
        abort(500)


def drop_line(lineno: str, chain: str = "PREROUTING") -> tuple[bytes, bytes]:
    p = Popen(["iptables", "-t", "nat", "-D", chain, lineno], stdout=PIPE, stderr=PIPE)
    return p.communicate()


def append_prerouting_rule(
    proto: str, host_ip: str, dest_ip: str, port: str
) -> tuple[bytes, bytes]:
    p = Popen(
        [
            "iptables",
            "-t",
            "nat",
            "-A",
            "PREROUTING",
            "-p",
            proto,
            "-d",
            host_ip,
            "--dport",
            port,
            "-j",
            "DNAT",
            "--to-destination",
            "%s:%s" % (dest_ip, port),
        ],
        stdout=PIPE,
        stderr=PIPE,
    )
    return p.communicate()


def append_postrouting_rule(
    proto: str, dest_ip: str
) -> tuple[bytes, bytes]:
    p = Popen(
        [
            "iptables",
            "-t",
            "nat",
            "-A",
            "POSTROUTING",
            "-p",
            proto,
            "-d",
            dest_ip,
            "-j",
            "MASQUERADE",
        ],
        stdout=PIPE,
        stderr=PIPE,
    )
    return p.communicate()


def get_table(table: str = "nat") -> str:
    p = Popen(["iptables", "-t", table, "-L", "-n", "--line-number"], stdout=PIPE)
    return p.communicate()[0].decode()


def prune_tables(
    protocols: list[str], host_ip: str, dest_ip: str, ports: list[str]
) -> None:
    iptable = get_table("nat")

    rules = iptable.split("\n")

    while True:
        if len(rules) == 0:
            break

        rule = rules.pop(0).strip()

        for proto in protocols:
            # PREROUTING RULES
            for port in ports:
                pattern = r"^([0-9]+)\s+DNAT\s+{proto}\s+\-\-\s+[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\/[0-9]+\s+{host_ip}\s+{proto}\s+dpt\:{dport}\s+to\:{dest_ip}:{dport}$".format(
                    proto=proto, host_ip=host_ip, dest_ip=dest_ip, dport=port
                )
                match = re.match(pattern, rule)
                if match:
                    lineno = match.groups()[0]
                    out, err = drop_line(lineno, chain="PREROUTING")
                    if not err:
                        iptable = get_table("nat")
                        rules = iptable.split("\n")
                    del out
                    del err

                # POSTROUTING RULE
                pattern = r"^([0-9]+)\s+MASQUERADE\s+{proto}\s+\-\-\s+0.0.0.0\/0\s+{dest_ip}$".format(
                    proto=proto, dest_ip=dest_ip
                )
                match = re.match(pattern, rule)
                if match:
                    lineno = match.groups()[0]
                    out, err = drop_line(lineno, chain="POSTROUTING")
                    if not err:
                        iptable = get_table("nat")
                        rules = iptable.split("\n")

                    del out
                    del err


def populate_tables(
    protocols: list[str], host_ip: str, dest_ip: str, ports: list[str]
) -> None:
    for proto in protocols:
        for port in ports:
            append_prerouting_rule(proto, host_ip, dest_ip, port)
        append_postrouting_rule(proto, dest_ip)


@app.route("/")
def index() -> str:
    if request.headers.getlist("X-Forwarded-For"):
        dest_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        dest_ip = request.remote_addr

    if not dest_ip:
        abort(400)

    last_host, last_ip = get_state()

    protocols = getenv("PROTOCOLS", "tcp").split(",")
    host_ip = getenv("HOST_IP")
    ports = getenv("PORTS", "").split(",")

    if not host_ip or len(ports) == 0 or len(protocols) == 0:
        raise Exception("Bad configuration")

    if last_host != host_ip:
        prune_tables(protocols, last_host, last_ip, ports)

    if dest_ip != last_ip:
        prune_tables(protocols, host_ip, last_ip, ports)

    if last_host != host_ip or dest_ip != last_ip:
        populate_tables(protocols, host_ip, dest_ip, ports)
        set_state(host_ip, dest_ip)

    return "%s:%s" % (host_ip, dest_ip)


if __name__ == "__main__":
    app.run(port=8080, debug=True)