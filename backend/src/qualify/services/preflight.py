from qualify.models.state import CheckResult, Server
from qualify.services import ssh_client
from qualify.services.keyring_store import get_sudo_password
from qualify.services.server_audit import AuditedConn


async def run_preflight(server: Server, audit_stage: str = "preflight") -> list[CheckResult]:
    results: list[CheckResult] = []

    try:
        raw_conn, _ = await ssh_client.get_connection(server)
        conn = AuditedConn(raw_conn, audit_stage, sudo_password=get_sudo_password(server.id))
    except Exception as e:
        return [CheckResult(check="ssh_connect", status="fail", message=str(e))]

    results.append(CheckResult(check="ssh_connect", status="pass", message="SSH connection established"))

    async def chk(name: str, cmd: str, parse_fn):
        try:
            rc, out, err = await ssh_client.exec_command(conn, cmd)
            results.append(parse_fn(rc, out.strip(), err.strip()))
        except Exception as e:
            results.append(CheckResult(check=name, status="skip", message=f"Error: {e}"))

    await chk("docker_installed", "docker --version",
        lambda rc, out, err: CheckResult(check="docker_installed",
            status="pass" if rc == 0 else "fail",
            message=out if rc == 0 else err or "Docker not found"))

    await chk("docker_running", "sudo docker info --format '{{.ServerVersion}}'",
        lambda rc, out, err: CheckResult(check="docker_running",
            status="pass" if rc == 0 else "fail",
            message=f"Docker Engine {out}" if rc == 0 else "Docker daemon not running"))

    await chk("docker_compose", "docker compose version",
        lambda rc, out, err: CheckResult(check="docker_compose",
            status="pass" if rc == 0 else "warn",
            message=out if rc == 0 else "docker compose plugin not found"))

    await chk("port_80", "ss -tlnp | grep ':80 '",
        lambda rc, out, err: CheckResult(check="port_80",
            status="pass" if not out else "warn",
            message="Port 80 is free" if not out else f"Port 80 in use: {out}"))

    await chk("port_443", "ss -tlnp | grep ':443 '",
        lambda rc, out, err: CheckResult(check="port_443",
            status="pass" if not out else "warn",
            message="Port 443 is free" if not out else f"Port 443 in use: {out}"))

    await chk("nginx_running", "systemctl is-active nginx 2>/dev/null || echo inactive",
        lambda rc, out, err: CheckResult(check="nginx_running",
            status="warn" if out == "active" else "pass",
            message="Nginx is active — will conflict with Traefik" if out == "active" else "Nginx not running"))

    await chk("apache_running", "systemctl is-active apache2 2>/dev/null || echo inactive",
        lambda rc, out, err: CheckResult(check="apache_running",
            status="warn" if out == "active" else "pass",
            message="Apache2 is active — will conflict with Traefik" if out == "active" else "Apache2 not running"))

    await chk("sudo_access", "sudo -n true 2>/dev/null && echo ok || echo fail",
        lambda rc, out, err: CheckResult(check="sudo_access",
            status="pass" if "ok" in out else "warn",
            message="Passwordless sudo available" if "ok" in out else "Sudo requires password (stored in keyring)"))

    await chk("firewall", "sudo ufw status | head -1",
        lambda rc, out, err: CheckResult(check="firewall",
            status="pass" if "active" in out.lower() else "warn",
            message="UFW active" if "active" in out.lower() else "UFW inactive — swarm ports may be exposed"))

    await chk("disk_space", "df -h / | tail -1 | awk '{print $5, $4}'",
        lambda rc, out, err: _parse_disk(out))

    await chk("memory", "free -m | awk '/^Mem:/{print $2, $7}'",
        lambda rc, out, err: _parse_memory(out))

    await chk("os_info", "grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '\"'",
        lambda rc, out, err: CheckResult(check="os_info", status="pass", message=out or "Unknown OS"))

    conn.close()
    return results


def _parse_disk(out: str) -> CheckResult:
    try:
        parts = out.split()
        pct = int(parts[0].rstrip("%"))
        avail = parts[1] if len(parts) > 1 else "?"
        status = "fail" if pct > 95 else "warn" if pct > 80 else "pass"
        return CheckResult(check="disk_space", status=status,
                           message=f"Disk {pct}% used, {avail} available")
    except Exception:
        return CheckResult(check="disk_space", status="skip", message=f"Could not parse: {out!r}")


def _parse_memory(out: str) -> CheckResult:
    try:
        parts = out.split()
        total = int(parts[0])
        avail = int(parts[1]) if len(parts) > 1 else 0
        status = "warn" if avail < 256 else "pass"
        return CheckResult(check="memory", status=status,
                           message=f"{avail} MB available of {total} MB total")
    except Exception:
        return CheckResult(check="memory", status="skip", message=f"Could not parse: {out!r}")
