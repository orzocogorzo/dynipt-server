from os import getenv
import re
from subprocess import Popen, PIPE
from pathlib import Path
from typing import Optional

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


def communicate(p: Popen) -> str:
    out, err = p.communicate(input=getenv("DYNIPT_PWD", "").encode())
    if err and not re.search(r"\[sudo\] password for", err.decode()):
        raise Exception(err.decode())

    if out:
        return out.decode()
    else:
        return ""


def drop_line(table_name: str, chain_name: str, lineno: str) -> None:
    p = Popen(
        ["sudo", "-S", "iptables", "-t", table_name, "-D", chain_name, lineno],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )

    communicate(p)


def append_filter_rule(proto: str, host_ip: str, dest_ip: str, port: str) -> str:
    p = Popen(
        [
            "sudo",
            "-S",
            "iptables",
            "-t",
            "filter",
            "-I",
            "DYNIPT_FORWARD",
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

    return communicate(p)


def append_prerouting_rule(proto: str, host_ip: str, dest_ip: str, port: str) -> str:
    p = Popen(
        [
            "sudo",
            "-S",
            "iptables",
            "-t",
            "nat",
            "-A",
            "DYNIPT_PREROUTING",
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

    return communicate(p)


def append_postrouting_rule(proto: str, dest_ip: str) -> str:
    p = Popen(
        [
            "sudo",
            "-S",
            "iptables",
            "-t",
            "nat",
            "-A",
            "DYNIPT_POSTROUTING",
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

    return communicate(p)


def insert_jump_rule(
    table_name: str,
    chain_name: str,
    dest_ip: str,
    proto: str,
    port: Optional[str] = None,
) -> None:
    custom_chain_name = "DYNIPT_" + chain_name
    command = [
        "sudo",
        "-S",
        "iptables",
        "-t",
        table_name,
        "-I",
        chain_name,
        "-p",
        proto,
        "-d",
        dest_ip,
        "-j",
        custom_chain_name,
    ]

    if port:
        command = (
            command[:-2]
            + [
                "--dport",
                port,
            ]
            + command[-2:]
        )

    p = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)

    communicate(p)


def create_chain(table_name: str, chain_name: str) -> None:
    p = Popen(
        ["sudo", "-S", "iptables", "-t", table_name, "-N", chain_name],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )

    communicate(p)


def get_table(table_name: str) -> str:
    p = Popen(
        ["sudo", "-S", "iptables", "-t", table_name, "-L", "-n", "--line-number"],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )

    return communicate(p)


def get_chain(table_name: str, chain_name: str) -> list[str]:
    iptable = get_table(table_name)
    rules = iptable.split("\n")

    chain_rules = []
    inside_chain = False
    for rule in rules:
        if not inside_chain:
            inside_chain = re.match(r"^Chain " + chain_name, rule)
            continue

        inside_chain = re.match(r"^Chain", rule) is None
        if not inside_chain:
            continue

        chain_rules.append(rule)

    return chain_rules


def prune_rule(
    table_name: str, chain_name: str, rule: str, pattern: str, index_delta: int = 0
) -> bool:
    match = re.match(pattern, rule)

    if match:
        lineno = match.groups()[0]
        drop_line(table_name, chain_name, str(int(lineno) + index_delta))
        return True

    return False


def delete_chain(table_name: str, chain_name: str) -> None:
    p = Popen(
        ["sudo", "-S", "iptables", "-t", table_name, "-X", chain_name],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )

    try:
        communicate(p)
    except:
        pass


def prune_tables() -> None:
    chains = [("filter", "FORWARD"), ("nat", "PREROUTING"), ("nat", "POSTROUTING")]
    for table_name, chain_name in chains:
        custom_chain = "DYNIPT_" + chain_name
        delete_chain(table_name, custom_chain)
        create_chain(table_name, custom_chain)
        prune_chain(table_name, chain_name)


def prune_chain(table_name: str, chain_name: str) -> None:
    rules = get_chain(table_name, chain_name)

    index_delta = 0
    for rule in rules:
        pattern = r"^([0-9]+)\s+DYNIPT_" + chain_name
        if prune_rule(table_name, chain_name, rule, pattern, index_delta):
            index_delta = index_delta - 1


def populate_tables(protocols: list, host_ip: str, dest_ip: str, ports: list) -> None:
    for proto in protocols:
        for port in ports:
            insert_jump_rule("filter", "FORWARD", host_ip, proto, port)
            insert_jump_rule("nat", "PREROUTING", host_ip, proto, port)
            append_filter_rule(proto, host_ip, dest_ip, port)
            append_prerouting_rule(proto, host_ip, dest_ip, port)

        insert_jump_rule("nat", "POSTROUTING", dest_ip, proto)
        append_postrouting_rule(proto, dest_ip)


def get_backup() -> str:
    p = Popen(["sudo", "-S", "iptables-save"], stdin=PIPE, stdout=PIPE, stderr=PIPE)

    return communicate(p)


def backup_resotre(backup: str) -> None:
    file_path = "/tmp/dynipt-v4.bak"
    with open(file_path, "w") as f:
        f.write(backup)
        p = Popen(["sudo", "-S", "iptables-restore", file_path])
        communicate(p)


@app.route("/")
def index() -> str:
    if request.headers.getlist("X-Forwarded-For"):
        dest_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        dest_ip = request.remote_addr

    if not dest_ip:
        return abort(400, "Remote ip not known")

    last_host, last_ip = get_state()

    protocols = getenv("DYNIPT_PROTOCOLS", "").split(",")
    host_ip = getenv("DYNIPT_HOST_IP")
    ports = getenv("DYNIPT_PORTS", "").split(",")

    if not host_ip or len(ports) == 0 or len(protocols) == 0:
        return abort(500, "Bad configuration")

    backup = None
    try:
        if last_host != host_ip or dest_ip != last_ip:
            backup = get_backup()
            prune_tables()
            populate_tables(protocols, host_ip, dest_ip, ports)
            set_state(host_ip, dest_ip)
    except Exception as e:
        if backup:
            backup_resotre(backup)
        return abort(500, description=str(e))

    return "%s:%s" % (host_ip, dest_ip)


if __name__ == "__main__":
    if getenv("DYNIPT_FRONT_SERVER") == "true":
        host = "127.0.0.1"
    else:
        host = "0.0.0.0"

    app.run(host=host, port=8080, debug=True)
