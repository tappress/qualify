"""Audit log for SSH commands executed on a server.

Each command is appended as a JSON line to /var/log/qualify/audit.log on the
remote server. The AuditedConn wrapper is a drop-in replacement for an
asyncssh.SSHClientConnection — it exposes the same .run() interface and
transparently records every command.
"""
from __future__ import annotations

import json
import re
import shlex
from datetime import datetime, timezone
from typing import Optional

import asyncssh

LOG_PATH = "~/.qualify/audit.log"
LOG_DIR = "~/.qualify"


_SUDO_RE = re.compile(r"\bsudo\b(?!\s+-[a-zA-Z]*S)")


class AuditedConn:
    """Wraps an asyncssh connection and logs every .run() call to the server.

    If sudo_password is provided, sudo commands are automatically rewritten to
    use `sudo -S` with the password injected via stdin so they work on servers
    that require a password for sudo.
    """

    def __init__(
        self,
        conn: asyncssh.SSHClientConnection,
        stage: str = "",
        sudo_password: Optional[str] = None,
    ) -> None:
        self._conn = conn
        self.stage = stage
        self._sudo_password = sudo_password

    async def run(self, command: str, **kwargs) -> asyncssh.SSHCompletedProcess:
        command, kwargs = self._inject_sudo(command, kwargs)
        try:
            result = await self._conn.run(command, **kwargs)
        except asyncssh.ProcessError as e:
            await self._append(command, e.exit_status or 1, e.stderr or "")
            raise
        await self._append(command, result.exit_status, result.stderr or "")
        return result

    def with_stage(self, stage: str) -> "AuditedConn":
        return AuditedConn(self._conn, stage, self._sudo_password)

    def close(self) -> None:
        self._conn.close()

    # ── internal ─────────────────────────────────────────────────────────────

    def _inject_sudo(self, command: str, kwargs: dict) -> tuple[str, dict]:
        """Rewrite sudo → sudo -S and inject password via stdin if needed."""
        if not self._sudo_password or "sudo" not in command:
            return command, kwargs
        modified = _SUDO_RE.sub("sudo -S", command)
        if "sudo -S" in modified:
            kwargs = {**kwargs, "input": self._sudo_password + "\n"}
        return modified, kwargs

    async def _append(self, command: str, rc: int, stderr: str) -> None:
        entry: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": self.stage,
            "cmd": command,
            "rc": rc,
        }
        if rc != 0 and stderr:
            entry["err"] = stderr[:400]

        try:
            safe = shlex.quote(json.dumps(entry))
            await self._conn.run(
                f"mkdir -p {LOG_DIR} && printf '%s\\n' {safe} >> {LOG_PATH}",
                check=False,
            )
        except Exception:
            pass  # logging must never break the main operation


async def fetch_log(conn: asyncssh.SSHClientConnection) -> list[dict]:
    """Read and parse the audit log from the server. Returns oldest-first."""
    result = await conn.run(f"cat {LOG_PATH} 2>/dev/null || true", check=False)
    entries = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries
