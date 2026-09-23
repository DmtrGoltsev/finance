"""Fail-closed approval and live-host checks for Finance delivery."""

from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import hashlib
import ipaddress
import json
import os
import platform
import re
import shutil
import socket
import subprocess
from pathlib import Path

PACKAGES = (
    "docker_ce",
    "docker_ce_cli",
    "containerd_io",
    "docker_buildx_plugin",
    "docker_compose_plugin",
)
IMAGES = ("postgres", "n8n", "gateway_node_base")
FIELDS = {
    "inventory_run_id", "captured_at_utc", "approved_at_utc", "approval_ticket",
    "host_name", "os_id", "os_version_id", "architecture", "min_cpus",
    "min_available_memory_mb", "min_free_disk_mb", "bridge_name", "bridge_subnet",
    "bridge_gateway", "callback_port", "n8n_port", "docker_packages", "images",
}
IMAGE_RE = re.compile(r"^[A-Za-z0-9./_-]+(?::[A-Za-z0-9._-]+)?@sha256:[a-f0-9]{64}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+~@-]{0,127}$")


class ContractError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _utc(value: str) -> dt.datetime:
    require(isinstance(value, str), "timestamp must be a string")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, binascii.Error) as exc:
        raise ContractError("timestamp must be ISO-8601 UTC") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() == dt.timedelta(0), "timestamp must be UTC")
    return parsed


def validate_approval(raw: bytes, now: dt.datetime | None = None) -> dict:
    try:
        approval = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ContractError("approval is not valid UTF-8 JSON") from exc
    require(type(approval) is dict and set(approval) == FIELDS, "approval fields are missing or unexpected")
    now = now or dt.datetime.now(dt.timezone.utc)
    captured = _utc(approval["captured_at_utc"])
    approved = _utc(approval["approved_at_utc"])
    require(dt.timedelta(0) <= now - captured <= dt.timedelta(hours=24), "host inventory is missing or older than 24 hours")
    require(captured <= approved <= now, "approval time must follow inventory and not be in the future")
    require(str(approval["inventory_run_id"]).isdigit(), "inventory_run_id must be numeric")
    for key in ("approval_ticket", "host_name", "bridge_name"):
        require(isinstance(approval[key], str) and TOKEN_RE.fullmatch(approval[key]) is not None, f"invalid {key}")
    require(approval["os_id"] in {"ubuntu", "debian"}, "Docker package install supports only approved Ubuntu/Debian hosts")
    require(isinstance(approval["os_version_id"], str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", approval["os_version_id"]) is not None, "invalid os_version_id")
    require(approval["architecture"] in {"x86_64", "aarch64"}, "unsupported architecture")
    for key, floor in (("min_cpus", 1), ("min_available_memory_mb", 3072), ("min_free_disk_mb", 8192)):
        require(type(approval[key]) is int and approval[key] >= floor, f"{key} must be at least {floor}")
    for key in ("callback_port", "n8n_port"):
        require(type(approval[key]) is int and 1024 <= approval[key] <= 65535, f"invalid {key}")
    require(approval["callback_port"] != approval["n8n_port"], "callback and n8n ports must differ")
    try:
        subnet = ipaddress.ip_network(approval["bridge_subnet"], strict=True)
        gateway = ipaddress.ip_address(approval["bridge_gateway"])
    except ValueError as exc:
        raise ContractError("invalid bridge subnet or gateway") from exc
    require(isinstance(subnet, ipaddress.IPv4Network) and subnet.is_private and subnet.prefixlen <= 29, "bridge must be a private IPv4 subnet with capacity")
    require(gateway == subnet.network_address + 1, "bridge gateway must be first usable address")
    require(approval["bridge_name"] == "finance_delivery_host_bridge", "bridge name must be Finance-owned")
    packages = approval["docker_packages"]
    require(type(packages) is dict and set(packages) == set(PACKAGES), "all Docker package versions must be pinned")
    for name, version in packages.items():
        require(isinstance(version, str) and TOKEN_RE.fullmatch(version) is not None, f"invalid package version: {name}")
    images = approval["images"]
    require(type(images) is dict and set(images) == set(IMAGES), "all production image digests are required")
    for name, image in images.items():
        require(isinstance(image, str) and IMAGE_RE.fullmatch(image) is not None, f"image is not digest-pinned: {name}")
    return approval


def approval_from_environment() -> dict:
    encoded = os.environ.get("FINANCE_DELIVERY_APPROVAL_B64", "")
    expected = os.environ.get("FINANCE_DELIVERY_APPROVAL_SHA256", "")
    require(re.fullmatch(r"[a-f0-9]{64}", expected) is not None, "approval SHA-256 is required")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ContractError("approval base64 is missing or invalid") from exc
    require(hashlib.sha256(raw).hexdigest() == expected, "approval SHA-256 mismatch")
    return validate_approval(raw)


def _os_release() -> dict[str, str]:
    result = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            result[key] = value.strip('"')
    return result


def _available_memory_mb() -> int:
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    raise ContractError("MemAvailable is unavailable")


def check_live_host(approval: dict, install_root: Path = Path("/opt/finance")) -> dict:
    require(platform.system() == "Linux", "production host must be Linux")
    os_release = _os_release()
    require(os_release.get("ID") == approval["os_id"] and os_release.get("VERSION_ID") == approval["os_version_id"], "host OS differs from approved inventory")
    require(platform.machine() == approval["architecture"], "host architecture differs from approved inventory")
    require(socket.gethostname() == approval["host_name"], "host name differs from approved inventory")
    cpus = os.cpu_count() or 0
    memory = _available_memory_mb()
    disk = shutil.disk_usage(install_root).free // (1024 * 1024)
    require(cpus >= approval["min_cpus"], "insufficient host CPUs")
    require(memory >= approval["min_available_memory_mb"], "insufficient available host memory")
    require(disk >= approval["min_free_disk_mb"], "insufficient free install disk")
    require(shutil.which("systemctl") is not None, "systemd is required")
    require(shutil.which("apt-get") is not None and shutil.which("apt-cache") is not None, "approved apt package manager is required")
    route_result = subprocess.run(["ip", "-j", "route", "show"], capture_output=True, text=True, check=False)
    require(route_result.returncode == 0, "host routes are unavailable; bridge overlap cannot be checked")
    bridge = ipaddress.ip_network(approval["bridge_subnet"])
    owned_bridge = _owned_bridge(approval)
    bridge_interface = None
    if owned_bridge:
        inspected = subprocess.run(["docker", "network", "inspect", approval["bridge_name"]],
                                   capture_output=True, text=True, check=False)
        network = json.loads(inspected.stdout)[0]
        bridge_interface = network.get("Options", {}).get("com.docker.network.bridge.name") or f"br-{network['Id'][:12]}"
    for route in json.loads(route_result.stdout):
        destination = route.get("dst", "default")
        if destination == "default":
            continue
        try:
            network = ipaddress.ip_network(destination, strict=False)
        except ValueError:
            continue
        if isinstance(network, ipaddress.IPv4Network) and bridge.overlaps(network):
            require(owned_bridge and route.get("dev") == bridge_interface and network == bridge,
                    "approved Docker bridge overlaps an unrelated host route")
    for key, port in (("n8n", approval["n8n_port"]), ("callback", approval["callback_port"])):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                require(key == "n8n" and _owned_n8n_port(port), f"{key} port is already in use")
    if owned_bridge:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            if connection.connect_ex((approval["bridge_gateway"], approval["callback_port"])) == 0:
                require(_owned_callback_proxy(approval), "callback bridge port is already in use")
    try:
        with socket.create_connection(("127.0.0.1", 8081), timeout=3):
            pass
    except OSError as exc:
        raise ContractError("Finance backend is not listening on 127.0.0.1:8081") from exc
    return {"os_id": os_release["ID"], "os_version_id": os_release["VERSION_ID"],
            "architecture": platform.machine(), "cpus": cpus,
            "available_memory_mb": memory, "free_disk_mb": disk}


def _owned_n8n_port(port: int) -> bool:
    result = subprocess.run(["docker", "ps", "--filter", "label=com.docker.compose.project=finance-n8n",
                             "--format", "{{.Ports}}"], capture_output=True, text=True, check=False)
    return result.returncode == 0 and f"127.0.0.1:{port}->5678/tcp" in result.stdout


def _owned_bridge(approval: dict) -> bool:
    result = subprocess.run(["docker", "network", "inspect", approval["bridge_name"]],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        return False
    try:
        network = json.loads(result.stdout)[0]
        address = network["IPAM"]["Config"]
    except (ValueError, KeyError, IndexError):
        return False
    return (network.get("Labels", {}).get("com.finance.owner") == "investment-delivery"
            and len(address) == 1 and address[0].get("Subnet") == approval["bridge_subnet"]
            and address[0].get("Gateway") == approval["bridge_gateway"])


def _owned_callback_proxy(approval: dict) -> bool:
    unit = Path("/etc/systemd/system/finance-investment-callback-proxy.service")
    if not unit.is_file() or unit.is_symlink():
        return False
    content = unit.read_text(encoding="utf-8")
    if not content.startswith("# Managed by Finance investment delivery release contract.\n"):
        return False
    if f"--bind {approval['bridge_gateway']} --subnet {approval['bridge_subnet']} --port {approval['callback_port']}" not in content:
        return False
    result = subprocess.run(["systemctl", "is-active", "--quiet", "finance-investment-callback-proxy.service"],
                            capture_output=True, check=False)
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("approval", "host-preflight"))
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args()
    try:
        approval = validate_approval(args.approval.read_bytes()) if args.approval else approval_from_environment()
        if args.mode == "host-preflight":
            print(json.dumps(check_live_host(approval), sort_keys=True))
        else:
            print("Finance delivery approval: valid and fresh")
    except (ContractError, OSError) as exc:
        parser.exit(2, f"DELIVERY_PREFLIGHT_BLOCKED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
