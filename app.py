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


def get_state() -> tuple:
    if not Path("var/state").is_file():
        Path("var/state").touch(mode=0o600)
        return ("", "")

    with open("var/state", "r") as f:
        address = tuple(f.read().split(":"))
        if len(address) != 2:
            return ("", "")

        return address


def set_state(host_ip, dest_ip: str) -> None:
    with open("var/state", "w") as f:
        f.write("%s:%s" % (host_ip, dest_ip))


def fetch_ip() -> str:
    conn = HTTPConnection("ip.yunhost.org")
    conn.request("GET", "/")
    res = conn.getresponse()
    if res.status == 200:
        return res.read().decode()
    else:
        abort(500)


def drop_line(lineno: str, table: str, chain: str = "PREROUTING") -> tuple:
    p = Popen(
        ["sudo", "-S", "iptables", "-t", table, "-D", chain, lineno],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
    return p.communicate(input=getenv("DYNIPT_PWD").encode())


def append_filter_rule(proto: str, host_ip: str, dest_ip: str, port: str) -> tuple:
    p = Popen(
        [
            "sudo",
            "-S",
            "iptables",
            "-t",
            "filter",
            "-I",
            "FORWARD",
            "-p",
            proto,
            "-s",
            host_ip,
            "-d",
            dest_ip,
            "--dport",
            port,
            "-j",
            "ACCEPT",
        ],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
    return p.communicate(input=getenv("DYNIPT_PWD").encode())


def append_prerouting_rule(proto: str, host_ip: str, dest_ip: str, port: str) -> tuple:
    p = Popen(
        [
            "sudo",
            "-S",
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
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
    return p.communicate(input=getenv("DYNIPT_PWD").encode())


def append_postrouting_rule(proto: str, dest_ip: str) -> tuple:
    p = Popen(
        [
            "sudo",
            "-S",
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
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
    return p.communicate(input=getenv("DYNIPT_PWD", "").encode())


def get_table(table: str = "nat") -> str:
    p = Popen(["iptables", "-t", table, "-L", "-n", "--line-number"], stdout=PIPE)
    return p.communicate()[0].decode()


def prune_postrouting(rule: str, proto: str, dest_ip: str) -> bool:
    pattern = (
        r"^([0-9]+)\s+MASQUERADE\s+{proto}\s+\-\-\s+0.0.0.0\/0\s+{dest_ip}$".format(
            proto=proto, dest_ip=dest_ip
        )
    )
    return prune_rule(pattern, rule, "nat", "POSTROUTING")


def prune_prerouting(
    rule: str, proto: str, host_ip: str, dest_ip: str, port: str
) -> bool:
    pattern = r"^([0-9]+)\s+DNAT\s+{proto}\s+\-\-\s+[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\/[0-9]+\s+{host_ip}\s+{proto}\s+dpt\:{dport}\s+to\:{dest_ip}:{dport}$".format(
        proto=proto, host_ip=host_ip, dest_ip=dest_ip, dport=port
    )
    return prune_rule(pattern, rule, "nat", "PREROUTING")


def prune_filter(rule: str, proto: str, host_ip: str, dest_ip: str, port: str) -> bool:
    pattern = r"^([0-9]+)\s+ACCEPT\s+{proto}\s+\-\-\s+{host_ip}\s+{dest_ip}\s+{proto}\s+dpt\:{port}".format(
        proto=proto, host_ip=host_ip, dest_ip=dest_ip, port=port
    )
    return prune_rule(pattern, rule, "filter", "FORWARD")


def prune_rule(pattern: str, rule: str, table: str, chain: str) -> bool:
    match = re.match(pattern, rule)
    if match:
        lineno = match.groups()[0]
        out, err = drop_line(lineno, table, chain=chain)
        if not err:
            return True
    return False


def prune_tables(protocols: list, host_ip: str, dest_ip: str, ports: list) -> None:
    prune_table("nat", protocols, host_ip, dest_ip, ports)
    prune_table("filter", protocols, host_ip, dest_ip, ports)


def prune_table(
    table: str, protocols: list, host_ip: str, dest_ip: str, ports: list
) -> None:
    iptable = get_table(table)
    rules = iptable.split("\n")

    while True:
        if len(rules) == 0:
            break

        rule = rules.pop(0).strip()

        for proto in protocols:
            for port in ports:
                match = False
                if table == "nat":
                    match = prune_prerouting(rule, proto, host_ip, dest_ip, port)
                else:
                    match = prune_filter(rule, proto, host_ip, dest_ip, port)

                if match:
                    iptable = get_table(table)
                    rules = iptable.split("\n")

            if table == "nat":
                match = prune_postrouting(rule, proto, dest_ip)
                if match:
                    iptable = get_table(table)
                    rules = iptable.split("\n")


def populate_tables(protocols: list, host_ip: str, dest_ip: str, ports: list) -> None:
    for proto in protocols:
        for port in ports:
            append_filter_rule(proto, host_ip, dest_ip, port)
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

    protocols = getenv("DYNIPT_PROTOCOLS", "tcp").split(",")
    host_ip = getenv("DYNIPT_HOST_IP")
    ports = getenv("DYNIPT_PORTS", "").split(",")

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
    if getenv("DYNIPT_FRONT_SERVER") == "true":
        host = "127.0.0.1"
    else:
        host = "0.0.0.0"

    app.run(host=host, port=8080, debug=True)
