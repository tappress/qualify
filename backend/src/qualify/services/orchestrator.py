import asyncio
import os
import shutil
import tempfile
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Optional

from qualify.models.state import Deployment, DeploymentStage, Environment, Process, Project, Server
from qualify.services import log_streamer, ssh_client, state_manager
from qualify.services.compose_gen import generate_compose
from qualify.services.provisioner.base import REGISTRY_PORT

STAGES = ["git_clone", "docker_build", "registry_push", "remote_pull", "compose_up", "health_check"]


def _parse_procfile(source_dir: str) -> list[Process]:
    """Parse a Procfile and return a list of Process objects.

    Format: one process per line — `name: command`
    Lines starting with # are ignored.
    Returns an empty list if no Procfile is found.
    """
    path = os.path.join(source_dir, "Procfile")
    if not os.path.exists(path):
        return []
    processes = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            name, _, command = line.partition(":")
            processes.append(Process(name=name.strip(), command=command.strip()))
    return processes


async def run_deployment(
    deployment_id: str,
    project: Project,
    env: Environment,
    server: Server,
    build_strategy: str,
    source_path: Optional[str] = None,
    cli_log: Optional[Callable[[str, str, str], None]] = None,
) -> None:
    """Run a full deployment pipeline.

    source_path: if provided, skip git clone and build from this local directory.
    cli_log:     optional callback(stage, msg, level) for CLI output; called in addition
                 to the SSE log streamer.
    """
    state = await state_manager.get_state()
    dep = next((d for d in state.deployments if d.id == deployment_id), None)
    if not dep:
        return

    dep.status = "running"
    dep.stages = [DeploymentStage(name=s) for s in STAGES]
    await state_manager.update_deployments(state.deployments)

    using_local_source = source_path is not None
    work_dir = source_path if using_local_source else tempfile.mkdtemp(prefix="qualify_")

    async def log(stage: str, msg: str, level: str = "info") -> None:
        await log_streamer.emit(deployment_id, stage, msg, level)
        if cli_log:
            cli_log(stage, msg, level)

    async def set_stage(name: str, status: str, ms: int | None = None) -> None:
        s = await state_manager.get_state()
        d = next((x for x in s.deployments if x.id == deployment_id), None)
        if d:
            for stage in d.stages:
                if stage.name == name:
                    stage.status = status
                    if ms is not None:
                        stage.duration_ms = ms
            await state_manager.update_deployments(s.deployments)

    def elapsed(t0: float) -> int:
        return int((asyncio.get_event_loop().time() - t0) * 1000)

    async def stream_proc(stage: str, *args) -> int:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        async for raw in proc.stdout:
            await log(stage, raw.decode().rstrip())
        await proc.wait()
        return proc.returncode

    async def run_proc(*args) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        out, _ = await proc.communicate()
        return proc.returncode, out.decode().strip()

    try:
        # ── git clone / local source ──────────────────────────────────────
        await set_stage("git_clone", "running")
        t0 = asyncio.get_event_loop().time()

        if using_local_source:
            await log("git_clone", f"Using local source: {work_dir}")
            _, sha = await run_proc("git", "-C", work_dir, "rev-parse", "--short", "HEAD")
            sha = sha or "local"
        else:
            await log("git_clone", f"Cloning {project.git_url} @ {project.git_branch}")
            rc = await stream_proc(
                "git_clone", "git", "clone", "--depth=1",
                "--branch", project.git_branch, project.git_url, work_dir,
            )
            if rc != 0:
                await set_stage("git_clone", "failed", elapsed(t0))
                raise RuntimeError("git clone failed")
            _, sha = await run_proc("git", "-C", work_dir, "rev-parse", "--short", "HEAD")

        s = await state_manager.get_state()
        d = next((x for x in s.deployments if x.id == deployment_id), None)
        if d:
            d.git_sha = sha
            await state_manager.update_deployments(s.deployments)

        await set_stage("git_clone", "success", elapsed(t0))
        await log("git_clone", f"SHA: {sha}")

        # ── read Procfile ─────────────────────────────────────────────────
        build_ctx = os.path.join(work_dir, project.build_context)
        detected = _parse_procfile(build_ctx)
        if detected and detected != project.processes:
            s = await state_manager.get_state()
            p = next((x for x in s.projects if x.id == project.id), None)
            if p:
                p.processes = detected
                await state_manager.update_projects(s.projects)
                project = p  # use updated project for compose generation
            names = ", ".join(proc.name for proc in detected)
            await log("git_clone", f"Procfile detected: {names}")

        # ── docker build ─────────────────────────────────────────────────
        await set_stage("docker_build", "running")
        t0 = asyncio.get_event_loop().time()

        image_name = project.image_name or f"qualify-{project.name}"
        image_tag = f"{image_name}:{sha}"
        dockerfile = os.path.join(work_dir, project.dockerfile_path)

        s = await state_manager.get_state()
        d = next((x for x in s.deployments if x.id == deployment_id), None)
        if d:
            d.image_tag = image_tag
            await state_manager.update_deployments(s.deployments)

        await log("docker_build", f"Building {image_tag}")

        if not os.path.exists(dockerfile):
            await set_stage("docker_build", "failed", elapsed(t0))
            raise RuntimeError(f"Dockerfile not found at {dockerfile}")

        rc = await stream_proc("docker_build", "docker", "build", "-t", image_tag, "-f", dockerfile, build_ctx)

        if rc != 0:
            await set_stage("docker_build", "failed", elapsed(t0))
            raise RuntimeError("docker build failed")
        await set_stage("docker_build", "success", elapsed(t0))

        # ── registry push ────────────────────────────────────────────────
        await set_stage("registry_push", "running")
        t0 = asyncio.get_event_loop().time()
        state_now = await state_manager.get_state()
        registry = state_now.settings.registry

        # Open SSH connection here — needed for tunnel during push and reused
        # through remote_pull and compose_up stages.
        await log("registry_push", f"Connecting to {server.host}")
        conn, _ = await ssh_client.get_connection(server)

        full_tag = image_tag

        if registry.url:
            full_tag = f"{registry.url}/{image_tag}"
            await run_proc("docker", "tag", image_tag, full_tag)

            # qualify-registry resolves to 127.0.0.1 on the server via /etc/hosts.
            # Push goes through an SSH tunnel so port 5000 never needs to be
            # publicly reachable.
            tunnel = await conn.forward_local_port("127.0.0.1", REGISTRY_PORT, "127.0.0.1", REGISTRY_PORT)
            try:
                rc = await stream_proc("registry_push", "docker", "push", full_tag)
            finally:
                tunnel.close()

            if rc != 0:
                await set_stage("registry_push", "failed", elapsed(t0))
                raise RuntimeError("docker push failed")
        else:
            await log("registry_push", "No registry configured — skipping push", "warn")

        await set_stage("registry_push", "success", elapsed(t0))

        # ── remote pull ──────────────────────────────────────────────────
        await set_stage("remote_pull", "running")
        t0 = asyncio.get_event_loop().time()

        if registry.url:
            # Server pulls from its own qualify-registry:5000 (HAProxy → registry:5001)
            rc, out, err = await ssh_client.exec_command(conn, f"docker pull {full_tag}")
            for line in (out + err).splitlines():
                await log("remote_pull", line)
            if rc != 0:
                await set_stage("remote_pull", "failed", elapsed(t0))
                raise RuntimeError(f"docker pull failed: {err}")
        else:
            await log("remote_pull", "No registry configured — skipping remote pull", "warn")

        await set_stage("remote_pull", "success", elapsed(t0))

        # ── compose up ───────────────────────────────────────────────────
        await set_stage("compose_up", "running")
        t0 = asyncio.get_event_loop().time()

        compose_yaml = generate_compose(project, env, full_tag)
        remote_dir = f"/opt/qualify/{project.name}/{env.name}"
        await ssh_client.exec_command(conn, f"mkdir -p {remote_dir}")
        await ssh_client.exec_command(
            conn,
            f"cat > {remote_dir}/docker-compose.yml << 'QUALIFY_EOF'\n{compose_yaml}\nQUALIFY_EOF",
        )

        await log("compose_up", "Running docker compose up -d")
        rc, out, err = await ssh_client.exec_command(
            conn, f"cd {remote_dir} && docker compose up -d --remove-orphans 2>&1"
        )
        for line in (out + err).splitlines():
            await log("compose_up", line)
        if rc != 0:
            await set_stage("compose_up", "failed", elapsed(t0))
            raise RuntimeError("docker compose up failed")

        conn.close()
        await set_stage("compose_up", "success", elapsed(t0))

        # ── health check ─────────────────────────────────────────────────
        await set_stage("health_check", "running")
        t0 = asyncio.get_event_loop().time()
        await asyncio.sleep(3)

        if env.domain:
            url = env.domain if env.domain.startswith("http") else f"https://{env.domain}"
            try:
                urllib.request.urlopen(url, timeout=10)
                await log("health_check", f"HTTP check passed: {url}")
            except Exception as e:
                await log("health_check", f"HTTP check warning: {e}", "warn")
        else:
            await log("health_check", "No domain configured — skipping HTTP check")

        await set_stage("health_check", "success", elapsed(t0))

        s = await state_manager.get_state()
        d = next((x for x in s.deployments if x.id == deployment_id), None)
        if d:
            d.status = "success"
            d.completed_at = datetime.now(timezone.utc)
            await state_manager.update_deployments(s.deployments)

        await log("health_check", "Deployment complete!")

    except Exception as exc:
        await log_streamer.emit(deployment_id, "error", str(exc), "error")
        if cli_log:
            cli_log("error", str(exc), "error")
        s = await state_manager.get_state()
        d = next((x for x in s.deployments if x.id == deployment_id), None)
        if d:
            d.status = "failed"
            d.error = str(exc)
            d.completed_at = datetime.now(timezone.utc)
            await state_manager.update_deployments(s.deployments)
    finally:
        await log_streamer.close_stream(deployment_id)
        if not using_local_source:
            shutil.rmtree(work_dir, ignore_errors=True)
