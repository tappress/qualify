import asyncio
import os
import time
from pathlib import Path

import asyncssh

from qualify.models.state import Server
from qualify.services.keyring_store import get_sudo_password


async def get_connection(server: Server) -> asyncssh.SSHClientConnection:
    key_path = os.path.expanduser(server.ssh_key_path)
    kwargs: dict = {
        "host": server.host,
        "port": server.port,
        "username": server.user,
        "known_hosts": None,
    }
    if Path(key_path).exists():
        kwargs["client_keys"] = [key_path]
    else:
        pw = get_sudo_password(server.id)
        if pw:
            kwargs["password"] = pw
    return await asyncssh.connect(**kwargs)


async def exec_command(conn: asyncssh.SSHClientConnection, command: str) -> tuple[int, str, str]:
    result = await conn.run(command, check=False)
    return result.exit_status, result.stdout or "", result.stderr or ""


async def test_connection(server: Server) -> tuple[bool, str, float]:
    t0 = time.monotonic()
    try:
        conn = await asyncio.wait_for(get_connection(server), timeout=10)
        rc, out, _ = await exec_command(conn, "echo qualify_ok")
        conn.close()
        latency = (time.monotonic() - t0) * 1000
        if rc == 0 and "qualify_ok" in out:
            return True, "Connection successful", latency
        return False, f"Unexpected response: {out!r}", latency
    except asyncio.TimeoutError:
        return False, "Connection timed out", (time.monotonic() - t0) * 1000
    except Exception as e:
        return False, str(e), (time.monotonic() - t0) * 1000
