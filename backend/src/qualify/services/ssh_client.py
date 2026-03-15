import asyncio
import os
import time
from pathlib import Path

import asyncssh

from qualify.models.state import Server
from qualify.services.keyring_store import get_sudo_password


async def get_connection(server: Server) -> tuple[asyncssh.SSHClientConnection, str]:
    """Returns (connection, auth_method) where auth_method is 'key' or 'password'."""
    key_path = os.path.expanduser(server.ssh_key_path) if server.ssh_key_path else None
    pw = get_sudo_password(server.id)
    kwargs: dict = {
        "host": server.host,
        "port": server.port,
        "username": server.user,
        "known_hosts": None,
    }
    has_key = bool(key_path and Path(key_path).exists())

    # If we already know which method works, use it directly
    if server.auth_method == "key" and has_key:
        return await asyncssh.connect(**kwargs, client_keys=[key_path]), "key"
    if server.auth_method == "password" and pw:
        return await asyncssh.connect(**kwargs, password=pw), "password"

    # First connect: try key → fall back to password
    if has_key:
        try:
            return await asyncssh.connect(**kwargs, client_keys=[key_path]), "key"
        except asyncssh.PermissionDenied:
            if pw:
                return await asyncssh.connect(**kwargs, password=pw), "password"
            raise
    if pw:
        return await asyncssh.connect(**kwargs, password=pw), "password"
    return await asyncssh.connect(**kwargs), "key"


async def exec_command(conn: asyncssh.SSHClientConnection, command: str) -> tuple[int, str, str]:
    result = await conn.run(command, check=False)
    return result.exit_status, result.stdout or "", result.stderr or ""


async def test_connection(server: Server) -> tuple[bool, str, float, str | None]:
    """Returns (success, message, latency_ms, auth_method)."""
    t0 = time.monotonic()
    try:
        conn, method = await asyncio.wait_for(get_connection(server), timeout=10)
        rc, out, _ = await exec_command(conn, "echo qualify_ok")
        conn.close()
        latency = (time.monotonic() - t0) * 1000
        if rc == 0 and "qualify_ok" in out:
            return True, "Connection successful", latency, method
        return False, f"Unexpected response: {out!r}", latency, None
    except asyncio.TimeoutError:
        return False, "Connection timed out", (time.monotonic() - t0) * 1000, None
    except Exception as e:
        return False, str(e), (time.monotonic() - t0) * 1000, None
