import yaml
from qualify.models.state import Environment, Project


def generate_compose(project: Project, env: Environment, image_tag: str) -> str:
    """
    Generate docker-compose.yml for a deployment.
    Build config comes from Project; runtime config (domain, port, env vars, infra) from Environment.
    """
    services: dict = {}
    volumes: dict = {}
    networks: dict = {}
    use_traefik = bool(env.domain)

    # ── App service ───────────────────────────────────────────────────────────
    app: dict = {"image": image_tag, "restart": "unless-stopped"}

    plain_env = {v.key: v.value for v in env.env_vars if not v.is_secret and v.value}
    if plain_env:
        app["environment"] = plain_env

    secret_names = [v.secret_name for v in env.env_vars if v.is_secret and v.secret_name]
    if secret_names:
        app["secrets"] = secret_names

    if use_traefik:
        router_name = f"{project.name}-{env.name}"
        app["networks"] = ["traefik_public", "internal"]
        app["labels"] = {
            "traefik.enable": "true",
            f"traefik.http.routers.{router_name}.rule": f"Host(`{env.domain}`)",
            f"traefik.http.routers.{router_name}.entrypoints": "websecure",
            f"traefik.http.routers.{router_name}.tls.certresolver": "le",
            f"traefik.http.services.{router_name}.loadbalancer.server.port": str(env.port),
        }
        networks["traefik_public"] = {"external": True}
        networks["internal"] = None
    else:
        app["ports"] = [f"{env.port}:{env.port}"]

    services["app"] = app

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
