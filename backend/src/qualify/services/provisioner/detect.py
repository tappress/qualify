from __future__ import annotations

import asyncssh
from pydantic import BaseModel, Field


class OSInfo(BaseModel):
    id: str      = Field(description='Raw value from /etc/os-release ID field, e.g. "ubuntu", "debian", "fedora"')
    name: str    = Field(description='Human-readable name from NAME field, e.g. "Ubuntu", "Debian GNU/Linux"')
    version: str = Field(description='Version string from VERSION_ID field, e.g. "22.04", "12"')
    family: str  = Field(description='Normalised distribution family: "debian", "rhel", "arch", "alpine"')


_FAMILY_MAP: dict[str, str] = {
    "ubuntu": "debian",
    "debian": "debian",
    "raspbian": "debian",
    "linuxmint": "debian",
    "pop": "debian",
    "elementary": "debian",
    "fedora": "rhel",
    "rhel": "rhel",
    "centos": "rhel",
    "rocky": "rhel",
    "almalinux": "rhel",
    "ol": "rhel",
    "arch": "arch",
    "manjaro": "arch",
    "alpine": "alpine",
}


def _parse_os_release(content: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"')
    return result


async def detect_os(conn: asyncssh.SSHClientConnection) -> OSInfo:
    result = await conn.run("cat /etc/os-release", check=False)
    if result.exit_status != 0:
        raise RuntimeError("Could not read /etc/os-release — is this a Linux server?")

    fields = _parse_os_release(result.stdout or "")
    os_id = fields.get("ID", "").lower()
    name = fields.get("NAME", os_id)
    version = fields.get("VERSION_ID", "")

    # ID_LIKE gives fallback families, e.g. "debian" for Ubuntu derivatives
    id_like = fields.get("ID_LIKE", "").lower().split()

    family = _FAMILY_MAP.get(os_id)
    if family is None:
        for like in id_like:
            family = _FAMILY_MAP.get(like)
            if family:
                break

    return OSInfo(id=os_id, name=name, version=version, family=family or os_id)
