from __future__ import annotations

from .base import BaseProvisioner
from .detect import OSInfo
from .ubuntu_debian import UbuntuDebianProvisioner


class UnsupportedOSError(Exception):
    pass


_SUPPORTED: dict[str, type[BaseProvisioner]] = {
    "debian": UbuntuDebianProvisioner,
}

SUPPORTED_NAMES = "Ubuntu, Debian"


def get_provisioner(os_info: OSInfo) -> BaseProvisioner:
    cls = _SUPPORTED.get(os_info.family)
    if cls is None:
        raise UnsupportedOSError(
            f"{os_info.name} {os_info.version} is not supported. "
            f"Supported distributions: {SUPPORTED_NAMES}."
        )
    return cls()
