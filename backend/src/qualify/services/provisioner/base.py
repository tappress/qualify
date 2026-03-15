from __future__ import annotations

import base64
from abc import ABC, abstractmethod

import asyncssh

# Private subnet for the WireGuard mesh. All Qualify servers join this network.
# First server always gets .1; subsequent servers get .2, .3, … (assigned by
# the control plane based on the count of already-bootstrapped servers).
#
# Uses RFC 6598 "Shared Address Space" (100.64.0.0/10) rather than RFC 1918.
# Hetzner (and other cloud providers) only support RFC 1918 for their private
# networks, so 100.64.x.x is guaranteed never to clash with provider-managed
# VPCs. Same reasoning Tailscale uses for their overlay network.
WG_SUBNET = "100.64.0"
WG_PORT = 51820

# Static hostname written to /etc/hosts on every server. All Docker images and
# compose files reference this name so the address never needs to change even if
# the registry moves to a different node.
REGISTRY_HOSTNAME = "qualify-registry"
REGISTRY_PORT = 5000      # HAProxy frontend (what clients use)
REGISTRY_BACKEND_PORT = 5001  # actual registry container port on host


class BaseProvisioner(ABC):
    """Distro-specific provisioner. Subclass one per supported OS family."""

    # ── Abstract: distro-specific ─────────────────────────────────────────────

    @abstractmethod
    async def install_docker(self, conn: asyncssh.SSHClientConnection) -> None:
        """Install Docker Engine using the distro's preferred method."""

    @abstractmethod
    async def install_package(self, conn: asyncssh.SSHClientConnection, package: str) -> None:
        """Install an OS package by name."""

    # ── Concrete helpers ──────────────────────────────────────────────────────

    async def _write_file(
        self,
        conn: asyncssh.SSHClientConnection,
        path: str,
        content: str,
        mode: str = "644",
    ) -> None:
        """Write content to a remote file using sudo, safe for any content."""
        encoded = base64.b64encode(content.encode()).decode()
        await conn.run(
            f"sudo sh -c 'echo {encoded} | base64 -d > {path} && chmod {mode} {path}'",
            check=False,
        )

    # ── Docker ────────────────────────────────────────────────────────────────

    async def ensure_docker(self, conn: asyncssh.SSHClientConnection) -> None:
        result = await conn.run("docker --version", check=False)
        if result.exit_status != 0:
            await self.install_docker(conn)

    # ── Docker Swarm ──────────────────────────────────────────────────────────

    async def ensure_swarm(self, conn: asyncssh.SSHClientConnection, advertise_addr: str = "") -> None:
        result = await conn.run(
            "sudo docker info --format '{{.Swarm.LocalNodeState}}'", check=False
        )
        if result.stdout.strip() != "active":
            addr_flag = f" --advertise-addr {advertise_addr}" if advertise_addr else ""
            await conn.run(f"sudo docker swarm init{addr_flag}", check=True)

    # ── Firewall ──────────────────────────────────────────────────────────────

    async def ensure_firewall(self, conn: asyncssh.SSHClientConnection, ssh_port: int = 22) -> None:
        """Configure UFW + DOCKER-USER iptables chain to secure Docker-published ports.

        UFW alone is insufficient: Docker bypasses it by injecting rules directly
        into iptables FORWARD/nat chains. The DOCKER-USER chain is processed
        before Docker's own DOCKER chain and cannot be bypassed.

        DOCKER-USER strategy: default-deny with a conntrack whitelist.
        - ESTABLISHED/RELATED: allow return traffic for connections Docker containers
          initiated outbound (e.g. pulling images, outbound API calls).
        - Port 80/443: allow new inbound connections (public HTTP/HTTPS via Traefik).
        - Everything else: DROP — any port Docker publishes is blocked from new
          inbound connections unless explicitly whitelisted here.

        This means Swarm management ports (2377, 7946, 4789), the private registry
        (5001), and any future Docker-published port are all blocked by default
        without needing per-port rules.
        """
        await self.install_package(conn, "ufw")

        ufw_rules = [
            "sudo ufw default deny incoming",
            "sudo ufw default allow outgoing",
            f"sudo ufw allow {ssh_port}/tcp",
            "sudo ufw allow 80/tcp",
            "sudo ufw allow 443/tcp",
            f"sudo ufw allow {WG_PORT}/udp",   # WireGuard — needed for multi-node peering
            "sudo ufw --force enable",
        ]
        for cmd in ufw_rules:
            await conn.run(cmd, check=False)

        # DOCKER-USER: default-deny with conntrack + port whitelist.
        # Rules are checked top-to-bottom; first match wins.
        # We INSERT whitelist rules at the top (so they precede DROP) and
        # APPEND the DROP rule (so it sits after all RETURN rules).
        # Each rule is idempotent via -C check-before-insert/append.
        whitelist = [
            # Return traffic for connections Docker containers opened outbound
            "-m conntrack --ctstate ESTABLISHED,RELATED -j RETURN",
            # Public HTTP/HTTPS — Traefik accepts new connections on these
            "-p tcp --dport 80 -j RETURN",
            "-p tcp --dport 443 -j RETURN",
        ]
        for rule in whitelist:
            await conn.run(
                f"sudo sh -c 'iptables -C DOCKER-USER {rule} 2>/dev/null"
                f" || iptables -I DOCKER-USER {rule}'",
                check=False,
            )

        # Blanket DROP at the end of the chain — blocks all other new inbound
        # connections to Docker-published ports regardless of which port they are.
        await conn.run(
            "sudo sh -c 'iptables -C DOCKER-USER -j DROP 2>/dev/null"
            " || iptables -A DOCKER-USER -j DROP'",
            check=False,
        )

        # Persist iptables rules across reboots
        await conn.run(
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent",
            check=False,
        )
        await conn.run("sudo netfilter-persistent save", check=False)

    # ── WireGuard ─────────────────────────────────────────────────────────────

    async def setup_wireguard(
        self,
        conn: asyncssh.SSHClientConnection,
        wg_ip: str,
    ) -> str:
        """Install WireGuard, assign wg_ip to wg0, and return the public key.

        Idempotent: if wg0 already exists the existing public key is returned.
        Peers are NOT configured here — that happens when a second server joins
        the Swarm and both sides exchange public keys.
        """
        # Already set up — return existing public key
        result = await conn.run("ip link show wg0 2>/dev/null && echo exists || echo missing", check=False)
        if "exists" in result.stdout:
            result = await conn.run("sudo cat /etc/wireguard/wg0.pub", check=False)
            return result.stdout.strip()

        await self.install_package(conn, "wireguard")

        # Generate key pair
        await conn.run("sudo sh -c 'wg genkey > /etc/wireguard/wg0.key'", check=False)
        await conn.run("sudo chmod 600 /etc/wireguard/wg0.key", check=False)
        await conn.run(
            "sudo sh -c 'wg pubkey < /etc/wireguard/wg0.key > /etc/wireguard/wg0.pub'",
            check=False,
        )

        # Write wg0.conf — $(cat ...) is evaluated by the inner sh, not the outer shell
        await conn.run(
            f"sudo sh -c '"
            f'printf "[Interface]\\nAddress = {wg_ip}/24\\n'
            f'PrivateKey = $(cat /etc/wireguard/wg0.key)\\n'
            f'ListenPort = {WG_PORT}\\n"'
            f" > /etc/wireguard/wg0.conf && chmod 600 /etc/wireguard/wg0.conf'",
            check=False,
        )

        await conn.run("sudo systemctl enable wg-quick@wg0", check=False)
        await conn.run("sudo wg-quick up wg0 2>/dev/null || true", check=False)

        result = await conn.run("sudo cat /etc/wireguard/wg0.pub", check=False)
        return result.stdout.strip()

    # ── HAProxy ───────────────────────────────────────────────────────────────

    async def setup_haproxy(self, conn: asyncssh.SSHClientConnection) -> None:
        """Install HAProxy and configure it to proxy qualify-registry:5000 → registry:5001.

        This provides a stable hostname for the registry that works identically
        on every node. When the registry moves (e.g. to a different Swarm node),
        only the HAProxy backend address changes — all image tags stay the same.
        """
        await self.install_package(conn, "haproxy")

        cfg = (
            "global\n"
            "    log /dev/log local0\n"
            "    maxconn 4096\n"
            "    daemon\n"
            "\n"
            "defaults\n"
            "    mode http\n"
            "    log global\n"
            "    timeout connect 5s\n"
            "    timeout client 1m\n"
            "    timeout server 1m\n"
            "\n"
            "frontend qualify_registry\n"
            f"    bind 127.0.0.1:{REGISTRY_PORT}\n"
            "    default_backend qualify_registry\n"
            "\n"
            "backend qualify_registry\n"
            f"    server registry 127.0.0.1:{REGISTRY_BACKEND_PORT} check\n"
        )
        await self._write_file(conn, "/etc/haproxy/haproxy.cfg", cfg)
        await conn.run("sudo systemctl enable haproxy", check=False)
        await conn.run("sudo systemctl restart haproxy", check=False)

        # Static hostname — all Docker configs reference qualify-registry:5000
        await conn.run(
            f"sudo sh -c '"
            f'grep -q "{REGISTRY_HOSTNAME}" /etc/hosts || '
            f'echo "127.0.0.1 {REGISTRY_HOSTNAME}" >> /etc/hosts'
            f"'",
            check=False,
        )

    # ── Registry ──────────────────────────────────────────────────────────────

    async def setup_registry(self, conn: asyncssh.SSHClientConnection) -> None:
        """Start a private Docker registry as a Swarm service.

        Uses mode=host port publishing so the registry port appears on the host
        network stack (accessible at 127.0.0.1:REGISTRY_BACKEND_PORT locally).
        The DOCKER-USER default-deny firewall blocks all new external connections
        to this port, so no authentication is required — the only inbound access
        paths are the local SSH tunnel and HAProxy on the same host.
        """
        result = await conn.run(
            "docker service inspect qualify-registry 2>/dev/null && echo exists || echo missing",
            check=False,
        )
        if "exists" in result.stdout:
            return

        await conn.run("sudo mkdir -p /opt/qualify/registry/data", check=False)
        await conn.run(
            "docker service create"
            " --name qualify-registry"
            f" --publish 'mode=host,published={REGISTRY_BACKEND_PORT},target=5000'"
            " --mount type=bind,source=/opt/qualify/registry/data,destination=/var/lib/registry"
            " --restart-condition any"
            " --constraint 'node.role==manager'"
            " registry:2",
            check=True,
        )

    # ── Bootstrap ─────────────────────────────────────────────────────────────

    async def bootstrap(
        self,
        conn: asyncssh.SSHClientConnection,
        advertise_addr: str = "",
        ssh_port: int = 22,
        wg_ip: str = f"{WG_SUBNET}.1",
    ) -> dict:
        """Full one-time server bootstrap. Returns WireGuard info."""
        await self.ensure_docker(conn)
        await conn.run("sudo usermod -aG docker $(whoami)", check=False)
        await self.ensure_swarm(conn, advertise_addr=advertise_addr)
        await self.ensure_firewall(conn, ssh_port=ssh_port)
        wg_public_key = await self.setup_wireguard(conn, wg_ip=wg_ip)
        await self.setup_haproxy(conn)
        await self.setup_registry(conn)
        return {"wg_ip": wg_ip, "wg_public_key": wg_public_key}
