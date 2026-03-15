from __future__ import annotations

from abc import ABC, abstractmethod

import asyncssh


class BaseProvisioner(ABC):
    """Distro-specific provisioner. Subclass one per supported OS family."""

    # ── Abstract: distro-specific ─────────────────────────────────────────────

    @abstractmethod
    async def install_docker(self, conn: asyncssh.SSHClientConnection) -> None:
        """Install Docker Engine using the distro's preferred method."""

    @abstractmethod
    async def install_package(self, conn: asyncssh.SSHClientConnection, package: str) -> None:
        """Install an OS package by name."""

    # ── Concrete: Docker / Swarm level (same everywhere) ─────────────────────

    async def ensure_docker(self, conn: asyncssh.SSHClientConnection) -> None:
        result = await conn.run("docker --version", check=False)
        if result.exit_status != 0:
            await self.install_docker(conn)

    async def ensure_swarm(self, conn: asyncssh.SSHClientConnection, advertise_addr: str = "") -> None:
        result = await conn.run(
            "sudo docker info --format '{{.Swarm.LocalNodeState}}'", check=False
        )
        if result.stdout.strip() != "active":
            addr_flag = f" --advertise-addr {advertise_addr}" if advertise_addr else ""
            await conn.run(f"sudo docker swarm init{addr_flag}", check=True)

    async def ensure_firewall(self, conn: asyncssh.SSHClientConnection, ssh_port: int = 22) -> None:
        """Configure UFW + DOCKER-USER iptables chain to block Swarm ports.

        UFW alone is insufficient: Docker bypasses it by injecting rules directly
        into iptables FORWARD/nat chains. The DOCKER-USER chain is processed
        before Docker's own DOCKER chain, so DROP rules there cannot be
        circumvented. Both layers are applied for defence-in-depth.
        """
        await self.install_package(conn, "ufw")

        ufw_rules = [
            "sudo ufw default deny incoming",
            "sudo ufw default allow outgoing",
            f"sudo ufw allow {ssh_port}/tcp",
            "sudo ufw allow 80/tcp",
            "sudo ufw allow 443/tcp",
            "sudo ufw deny 2377/tcp",
            "sudo ufw deny 7946/tcp",
            "sudo ufw deny 7946/udp",
            "sudo ufw deny 4789/udp",
            "sudo ufw --force enable",
        ]
        for cmd in ufw_rules:
            await conn.run(cmd, check=False)

        # DOCKER-USER rules — enforced before Docker's own chains; idempotent
        # via check-before-insert. Each rule uses a single sudo invocation so
        # the password isn't consumed twice by a compound || command.
        for proto, port in [("tcp", "2377"), ("tcp", "7946"), ("udp", "7946"), ("udp", "4789")]:
            await conn.run(
                f"sudo sh -c 'iptables -C DOCKER-USER -p {proto} --dport {port} -j DROP 2>/dev/null"
                f" || iptables -I DOCKER-USER -p {proto} --dport {port} -j DROP'",
                check=False,
            )

        # Persist iptables rules across reboots
        await conn.run(
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent",
            check=False,
        )
        await conn.run("sudo netfilter-persistent save", check=False)

    async def bootstrap(self, conn: asyncssh.SSHClientConnection, advertise_addr: str = "", ssh_port: int = 22) -> None:
        """Full one-time server bootstrap: Docker + Swarm + firewall."""
        await self.ensure_docker(conn)
        await conn.run("sudo usermod -aG docker $(whoami)", check=False)
        await self.ensure_swarm(conn, advertise_addr=advertise_addr)
        await self.ensure_firewall(conn, ssh_port=ssh_port)
