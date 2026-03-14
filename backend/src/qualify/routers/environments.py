from fastapi import APIRouter, HTTPException
from qualify.models.state import (
    Deployment, EnvVarCheck, Environment, EnvironmentCreate, EnvironmentUpdate,
    InfraInference,
)
from qualify.services import state_manager
from qualify.services.env_parser import parse_env_template
from qualify.services.keyring_store import get_cloudflare_token

router = APIRouter()


@router.get("/", response_model=list[Environment])
async def list_environments():
    state = await state_manager.get_state()
    return state.environments


@router.post("/", response_model=Environment, status_code=201)
async def create_environment(project_id: str, body: EnvironmentCreate):
    state = await state_manager.get_state()

    project = next((p for p in state.projects if p.id == project_id), None)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")

    server = next((s for s in state.servers if s.id == body.server_id), None)
    if not server:
        raise HTTPException(404, f"Server {body.server_id} not found")

    env = Environment(
        project_id=project_id,
        name=body.name,
        server_id=body.server_id,
        domain=body.domain,
        port=body.port,
        env_vars=body.env_vars,
    )

    # Infer infra from project's env template
    if project.env_template_content:
        env.inferred_infra = parse_env_template(project.env_template_content)

    # Auto DNS via Cloudflare if requested
    if body.auto_dns and body.domain:
        cf_record_id = await _create_cloudflare_record(
            body.domain, server.public_ip or server.host, state.settings
        )
        if cf_record_id:
            env.cloudflare_record_id = cf_record_id

    state.environments.append(env)
    await state_manager.update_environments(state.environments)
    return env


@router.get("/{environment_id}", response_model=Environment)
async def get_environment(environment_id: str):
    env = await state_manager.get_environment(environment_id)
    if not env:
        raise HTTPException(404, f"Environment {environment_id} not found")
    return env


@router.put("/{environment_id}", response_model=Environment)
async def update_environment(environment_id: str, body: EnvironmentUpdate):
    state = await state_manager.get_state()
    env = next((e for e in state.environments if e.id == environment_id), None)
    if not env:
        raise HTTPException(404, f"Environment {environment_id} not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(env, field, val)
    await state_manager.update_environments(state.environments)
    return env


@router.delete("/{environment_id}")
async def delete_environment(environment_id: str):
    state = await state_manager.get_state()
    env = next((e for e in state.environments if e.id == environment_id), None)
    if not env:
        raise HTTPException(404, f"Environment {environment_id} not found")

    # Clean up Cloudflare DNS record if we created it
    if env.cloudflare_record_id:
        await _delete_cloudflare_record(env.cloudflare_record_id, state.settings)

    state.environments = [e for e in state.environments if e.id != environment_id]
    await state_manager.update_environments(state.environments)
    return {"ok": True}


@router.get("/{environment_id}/deployments", response_model=list[Deployment])
async def environment_deployments(environment_id: str):
    state = await state_manager.get_state()
    return [d for d in state.deployments if d.environment_id == environment_id]


@router.get("/{environment_id}/preflight-env", response_model=list[EnvVarCheck])
async def preflight_env(environment_id: str):
    """
    Diff the project's .env.template against what this environment has configured.
    Returns a per-key status: provided | will_provision | missing.
    """
    state = await state_manager.get_state()
    env = next((e for e in state.environments if e.id == environment_id), None)
    if not env:
        raise HTTPException(404, f"Environment {environment_id} not found")

    project = next((p for p in state.projects if p.id == env.project_id), None)
    if not project:
        raise HTTPException(404, f"Project {env.project_id} not found")

    if not project.env_template_content:
        return []

    # Keys present in the template
    template_keys = [
        line.split("=", 1)[0].strip()
        for line in project.env_template_content.splitlines()
        if line.strip() and not line.strip().startswith("#") and "=" in line
    ]

    # Keys configured in this environment
    configured_keys = {v.key for v in env.env_vars if v.value or v.secret_name}

    # Keys that will be auto-provisioned by inferred infra
    provisioned_keys: set[str] = set()
    if env.inferred_infra.postgres:
        provisioned_keys.update({"DATABASE_URL", "POSTGRES_URL", "DB_URL"})
    if env.inferred_infra.redis:
        provisioned_keys.update({"REDIS_URL", "REDIS_HOST"})

    checks: list[EnvVarCheck] = []
    for key in template_keys:
        if key in configured_keys:
            checks.append(EnvVarCheck(key=key, status="provided"))
        elif any(key.startswith(p) for p in provisioned_keys) or key in provisioned_keys:
            checks.append(EnvVarCheck(
                key=key, status="will_provision",
                note="Will be set automatically by Qualify during provisioning",
            ))
        else:
            checks.append(EnvVarCheck(key=key, status="missing"))

    return checks


# ── Cloudflare helpers ────────────────────────────────────────────────────────

async def _create_cloudflare_record(domain: str, ip: str, settings) -> str | None:
    token = get_cloudflare_token()
    if not token or not settings.cloudflare_zone_id or not ip:
        return None
    try:
        import urllib.request
        import json

        # Extract subdomain name (e.g. "dev.myapp.com" → name="dev.myapp.com")
        payload = json.dumps({
            "type": "A",
            "name": domain,
            "content": ip,
            "ttl": 1,       # Auto TTL
            "proxied": False,
        }).encode()

        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/zones/{settings.cloudflare_zone_id}/dns_records",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                return result["result"]["id"]
    except Exception:
        pass
    return None


async def _delete_cloudflare_record(record_id: str, settings) -> None:
    token = get_cloudflare_token()
    if not token or not settings.cloudflare_zone_id:
        return
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/zones/{settings.cloudflare_zone_id}/dns_records/{record_id}",
            headers={"Authorization": f"Bearer {token}"},
            method="DELETE",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass
