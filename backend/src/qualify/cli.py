"""qualify CLI — directory-aware deployment commands.

qualify link    — link current directory to a project/service
qualify deploy  — deploy current directory to an environment
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

from qualify.models.state import Deployment, Environment, Project
from qualify.services import state_manager
from qualify.services.orchestrator import run_deployment

QUALIFY_FILE = ".qualify"


# ── .qualify file I/O ─────────────────────────────────────────────────────────

def _find_qualify_file(start: str = ".") -> tuple[dict, str] | tuple[None, None]:
    """Walk up directory tree to find the nearest .qualify file.
    Returns (data_dict, directory) or (None, None) if not found.
    """
    if tomllib is None:
        _die("tomllib not available — install Python 3.11+ or `pip install tomli`")
    current = os.path.abspath(start)
    while True:
        candidate = os.path.join(current, QUALIFY_FILE)
        if os.path.exists(candidate):
            with open(candidate, "rb") as f:
                return tomllib.load(f), current
        parent = os.path.dirname(current)
        if parent == current:
            return None, None
        current = parent


def _detect_git_url(directory: str = ".") -> str:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=directory, capture_output=True, text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except FileNotFoundError:
        return ""


def _write_qualify_file(data: dict, directory: str = ".") -> None:
    path = os.path.join(directory, QUALIFY_FILE)
    lines = [f'{k} = "{v}"' for k, v in data.items()]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {label}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val or default


def _die(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"✓ {msg}")


# ── qualify link ──────────────────────────────────────────────────────────────

def cmd_link(args: argparse.Namespace) -> None:
    existing, existing_dir = _find_qualify_file()
    if existing and existing_dir == os.path.abspath("."):
        print(f"Already linked → project={existing['project']!r}, service={existing['service']!r}")
        answer = _prompt("Overwrite?", "n")
        if answer.lower() != "y":
            return

    project_name = args.project or _prompt("Project name")
    if not project_name:
        _die("Project name is required.")

    default_service = os.path.basename(os.path.abspath("."))
    service_name = args.service or _prompt("Service name", default_service)
    if not service_name:
        _die("Service name is required.")

    asyncio.run(_link_async(project_name, service_name, args.env))


async def _link_async(project_name: str, service_name: str, env_name: str) -> None:
    state = await state_manager.get_state()

    project = next(
        (p for p in state.projects if p.group == project_name and p.name == service_name),
        None,
    )

    if project is None:
        print(f"\nService '{service_name}' not found in project '{project_name}' — creating it.")

        git_url = _detect_git_url()
        if git_url:
            print(f"  Git URL: {git_url}")
        else:
            git_url = _prompt("Git URL (leave blank for local-only builds)", "")
        domain = _prompt("Domain (e.g. api.myapp.com)", "")

        if not state.servers:
            _die("No servers found. Add a server via the Qualify UI first.")

        print("\n  Available servers:")
        for i, s in enumerate(state.servers, 1):
            status_note = f"  [{s.status}]" if s.status != "qualified" else ""
            print(f"    {i}. {s.name} ({s.host}){status_note}")
        choice = _prompt("Select server", "1")
        try:
            server = state.servers[int(choice) - 1]
        except (ValueError, IndexError):
            _die("Invalid selection.")

        project = Project(
            name=service_name,
            group=project_name,
            git_url=git_url,
            image_name=f"{project_name}-{service_name}",
        )
        state.projects.append(project)
        await state_manager.update_projects(state.projects)
        print(f"  Created service '{service_name}' in project '{project_name}'")

        env = Environment(
            project_id=project.id,
            name=env_name,
            server_id=server.id,
            domain=domain or "",
        )
        state.environments.append(env)
        await state_manager.update_environments(state.environments)
        print(f"  Created environment '{env_name}' on {server.name}")
    else:
        print(f"\n  Found service '{service_name}' in project '{project_name}'")
        env = next(
            (e for e in state.environments if e.project_id == project.id and e.name == env_name),
            None,
        )
        if env is None:
            if not state.servers:
                _die("No servers found. Add a server via the Qualify UI first.")
            print("\n  Available servers:")
            for i, s in enumerate(state.servers, 1):
                print(f"    {i}. {s.name} ({s.host})")
            choice = _prompt(f"Select server for environment '{env_name}'", "1")
            try:
                server = state.servers[int(choice) - 1]
            except (ValueError, IndexError):
                _die("Invalid selection.")
            domain = _prompt("Domain (e.g. api.myapp.com)", "")
            env = Environment(
                project_id=project.id,
                name=env_name,
                server_id=server.id,
                domain=domain or "",
            )
            state.environments.append(env)
            await state_manager.update_environments(state.environments)
            print(f"  Created environment '{env_name}' on {server.name}")
        else:
            server = next((s for s in state.servers if s.id == env.server_id), None)
            print(f"  Environment '{env_name}' → {server.name if server else '?'}")

    _write_qualify_file({"project": project_name, "service": service_name})
    print()
    _ok(f"Linked {project_name}/{service_name} → {env_name}")
    if env.domain:
        print(f"  domain: {env.domain}")
    print()
    print("  Next steps:")
    print(f"    qualify deploy             — deploy to {env_name}")
    print(f"    qualify deploy --env dev   — deploy to another environment")


# ── qualify deploy ────────────────────────────────────────────────────────────

def cmd_deploy(args: argparse.Namespace) -> None:
    asyncio.run(_deploy_async(args.env))


async def _deploy_async(env_name: Optional[str]) -> None:
    qualify_data, qualify_dir = _find_qualify_file()

    if qualify_data is None:
        # First deploy — run link flow inline, then continue
        print("No .qualify file found — setting up this directory first.\n")
        project_name = _prompt("Project name")
        if not project_name:
            _die("Project name is required.")
        default_service = os.path.basename(os.path.abspath("."))
        service_name = _prompt("Service name", default_service)
        resolved_env = env_name or "production"
        await _link_async(project_name, service_name, resolved_env)
        qualify_data, qualify_dir = _find_qualify_file()
        if qualify_data is None:
            _die("Setup failed.")
        print()

    project_name: str = qualify_data["project"]
    service_name: str = qualify_data["service"]
    source_path: str = qualify_dir  # type: ignore[assignment]

    state = await state_manager.get_state()

    project = next(
        (p for p in state.projects if p.group == project_name and p.name == service_name),
        None,
    )
    if project is None:
        _die(
            f"Service '{service_name}' not found in project '{project_name}'.\n"
            "  Run `qualify link` to re-link this directory."
        )

    project_envs = [e for e in state.environments if e.project_id == project.id]
    if not project_envs:
        _die("No environments configured for this service. Run `qualify link`.")

    if env_name:
        env = next((e for e in project_envs if e.name == env_name), None)
        if env is None:
            available = ", ".join(e.name for e in project_envs)
            _die(f"Environment '{env_name}' not found. Available: {available}")
    elif len(project_envs) == 1:
        env = project_envs[0]
    else:
        print("  Available environments:")
        for i, e in enumerate(project_envs, 1):
            server = next((s for s in state.servers if s.id == e.server_id), None)
            print(f"    {i}. {e.name} ({server.name if server else '?'})")
        choice = _prompt("Select environment", "1")
        try:
            env = project_envs[int(choice) - 1]
        except (ValueError, IndexError):
            _die("Invalid selection.")

    server = next((s for s in state.servers if s.id == env.server_id), None)
    if server is None:
        _die(f"Server not found for environment '{env.name}'.")

    # Check for Dockerfile before starting — give actionable guidance if missing
    dockerfile = os.path.join(source_path, project.build_context, project.dockerfile_path)
    if not os.path.exists(dockerfile):
        print(f"\n✗ No Dockerfile found at {dockerfile}\n")
        print("  Qualify builds directly from your Dockerfile for transparent,")
        print("  optimized images. Ask your AI assistant to generate one:\n")
        print("  ┌─────────────────────────────────────────────────────────────┐")
        print("  │ Write a production-ready multi-stage Dockerfile for this    │")
        print("  │ project. Use a minimal base image (alpine where possible),  │")
        print("  │ expose the correct port, and handle environment variables   │")
        print("  │ via ENV / ARG — no hardcoded secrets.                       │")
        print("  └─────────────────────────────────────────────────────────────┘")
        print("\n  Then run `qualify deploy` again.")
        sys.exit(1)

    print(f"\n→ {project_name}/{service_name}  →  {env.name}  ({server.name})")
    if env.domain:
        print(f"  {env.domain}")
    print()

    deployment = Deployment(
        project_id=project.id,
        environment_id=env.id,
        build_strategy=project.build_strategy,
    )
    state.deployments.append(deployment)
    await state_manager.update_deployments(state.deployments)

    t_start = time.monotonic()
    current_stage: list[str] = [""]
    stage_start: list[float] = [time.monotonic()]

    def cli_log(stage: str, msg: str, level: str = "info") -> None:
        if stage != current_stage[0]:
            current_stage[0] = stage
            stage_start[0] = time.monotonic()
            icon = {"warn": "⚠", "error": "✗"}.get(level, "·")
            print(f"  {icon} {stage}")
        prefix = {"warn": "    ⚠ ", "error": "    ✗ "}.get(level, "    ")
        print(f"{prefix}{msg}")

    await run_deployment(
        deployment.id,
        project,
        env,
        server,
        project.build_strategy,
        source_path=source_path,
        cli_log=cli_log,
    )

    state = await state_manager.get_state()
    dep = next((d for d in state.deployments if d.id == deployment.id), None)
    total = int(time.monotonic() - t_start)
    print()
    if dep and dep.status == "success":
        _ok(f"Deployed in {total}s")
        if env.domain:
            proto = "" if env.domain.startswith("http") else "https://"
            print(f"  → {proto}{env.domain}")
    else:
        error = dep.error if dep else "unknown error"
        _die(f"Deployment failed after {total}s: {error}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="qualify",
        description="Qualify — local-first PaaS CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", metavar="COMMAND")

    p_link = sub.add_parser("link", help="Link current directory to a project/service")
    p_link.add_argument("--project", metavar="NAME", help="Project (app group) name")
    p_link.add_argument("--service", metavar="NAME", help="Service name (default: directory name)")
    p_link.add_argument("--env", metavar="NAME", default="production", help="Environment name (default: production)")

    p_deploy = sub.add_parser("deploy", help="Deploy current directory to an environment")
    p_deploy.add_argument("--env", metavar="NAME", default=None, help="Target environment (default: auto-detect)")

    args = parser.parse_args()

    if args.cmd == "link":
        cmd_link(args)
    elif args.cmd == "deploy":
        cmd_deploy(args)
    else:
        parser.print_help()
