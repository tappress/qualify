from __future__ import annotations

import asyncssh

from .base import BaseProvisioner


class UbuntuDebianProvisioner(BaseProvisioner):
    """Provisioner for Ubuntu and Debian-family distributions."""

    async def install_package(self, conn: asyncssh.SSHClientConnection, package: str) -> None:
        await conn.run(
            f"sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {package}",
            check=True,
        )

    async def install_docker(self, conn: asyncssh.SSHClientConnection) -> None:
        # Official Docker install script — works on Ubuntu and Debian
        commands = [
            "sudo DEBIAN_FRONTEND=noninteractive apt-get update -y",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl",
            "sudo install -m 0755 -d /etc/apt/keyrings",
            "sudo curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo $ID)/gpg "
            "-o /etc/apt/keyrings/docker.asc",
            "sudo chmod a+r /etc/apt/keyrings/docker.asc",
            'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] '
            "https://download.docker.com/linux/$(. /etc/os-release && echo $ID) "
            '$(. /etc/os-release && echo $VERSION_CODENAME) stable" '
            "| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get update -y",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "
            "docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
            "sudo systemctl enable --now docker",
        ]
        for cmd in commands:
            await conn.run(cmd, check=True)
