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

    async def ensure_swarm(self, conn: asyncssh.SSHClientConnection) -> None:
        result = await conn.run(
            "docker info --format '{{.Swarm.LocalNodeState}}'", check=False
        )
        if result.stdout.strip() != "active":
            await conn.run("sudo docker swarm init", check=True)

    async def bootstrap(self, conn: asyncssh.SSHClientConnection) -> None:
        """Full one-time server bootstrap: Docker + Swarm."""
        await self.ensure_docker(conn)
        await self.ensure_swarm(conn)
