import yaml
from qualify.models.state import Environment, Process, Project


def generate_compose(project: Project, env: Environment, image_tag: str) -> str:
    """Generate docker-compose.yml for a deployment.

    If project.processes is populated (from a Procfile), one service is created
    per process using the same image. Only the process named "web" receives
    Traefik routing labels — all others run as internal background services.

    If project.processes is empty, a single "web" process is assumed (current
    single-container behaviour).
    """
    processes = project.processes or [Process(name="web", command="")]

    services: dict = {}
    volumes: dict = {}
    networks: dict = {}
    secret_names: list[str] = []
    use_traefik = bool(env.domain)

    if use_traefik:
        networks["traefik_public"] = {"external": True}
        networks["internal"] = None

    plain_env = {v.key: v.value for v in env.env_vars if not v.is_secret and v.value}
    proc_secrets = [v.secret_name for v in env.env_vars if v.is_secret and v.secret_name]

    for proc in processes:
        is_web = proc.name == "web"
        svc_name = f"{project.name}-{proc.name}" if len(processes) > 1 else "app"

        svc: dict = {
            "image": image_tag,
            "restart": "unless-stopped",
        }

        if proc.command:
            svc["command"] = proc.command

        if plain_env:
            svc["environment"] = plain_env

        if proc_secrets:
            svc["secrets"] = proc_secrets
            secret_names.extend(proc_secrets)

        if proc.replicas > 1:
            svc["deploy"] = {"replicas": proc.replicas}

        if use_traefik and is_web:
            router_name = f"{project.name}-{env.name}"
            svc.setdefault("deploy", {})["labels"] = {
                "traefik.enable": "true",
                f"traefik.http.routers.{router_name}.rule": f"Host(`{env.domain}`)",
                f"traefik.http.routers.{router_name}.entrypoints": "websecure",
                f"traefik.http.routers.{router_name}.tls.certresolver": "le",
                f"traefik.http.services.{router_name}.loadbalancer.server.port": str(env.port),
            }
            svc["networks"] = ["traefik_public", "internal"]
        elif use_traefik:
            # background process — internal network only, no public routing
            svc["networks"] = ["internal"]
        else:
            if is_web:
                svc["ports"] = [f"{env.port}:{env.port}"]

        services[svc_name] = svc

    # ── Postgres ──────────────────────────────────────────────────────────────
    if env.inferred_infra.postgres:
        pg_secret = f"qualify_{project.name}_{env.name}_pg_password"
        services["postgres"] = {
            "image": "postgres:16-alpine",
            "restart": "unless-stopped",
            "secrets": [pg_secret],
            "environment": {
                "POSTGRES_DB": "app",
                "POSTGRES_USER": "app",
                "POSTGRES_PASSWORD_FILE": f"/run/secrets/{pg_secret}",
            },
            "volumes": [f"postgres_{env.name}_data:/var/lib/postgresql/data"],
            **({"networks": ["internal"]} if use_traefik else {}),
        }
        volumes[f"postgres_{env.name}_data"] = None
        secret_names.append(pg_secret)

    # ── Redis ─────────────────────────────────────────────────────────────────
    if env.inferred_infra.redis:
        services["redis"] = {
            "image": "redis:7-alpine",
            "restart": "unless-stopped",
            **({"networks": ["internal"]} if use_traefik else {}),
        }

    # ── Assemble ──────────────────────────────────────────────────────────────
    compose: dict = {"services": services}
    if volumes:
        compose["volumes"] = volumes
    if networks:
        compose["networks"] = networks

    all_secrets = list(dict.fromkeys(secret_names))
    if all_secrets:
        compose["secrets"] = {name: {"external": True} for name in all_secrets}

    return yaml.dump(compose, default_flow_style=False, sort_keys=False)
