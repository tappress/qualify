import asyncio
from datetime import datetime, timezone
from pathlib import Path

from qualify.models.state import AppSettings, Deployment, Environment, Project, Server, StateModel

STATE_PATH = Path.home() / ".config" / "qualify" / "state.json"

_lock = asyncio.Lock()
_state: StateModel | None = None


def _load() -> StateModel:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if STATE_PATH.exists():
        return StateModel.model_validate_json(STATE_PATH.read_text())
    return StateModel()


def _save(state: StateModel) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = datetime.now(timezone.utc)
    STATE_PATH.write_text(state.model_dump_json(indent=2))


async def get_state() -> StateModel:
    global _state
    async with _lock:
        if _state is None:
            _state = _load()
        return _state


async def _mutate(fn) -> StateModel:
    global _state
    async with _lock:
        if _state is None:
            _state = _load()
        fn(_state)
        _save(_state)
        return _state


async def update_servers(servers: list[Server]) -> StateModel:
    return await _mutate(lambda s: setattr(s, "servers", servers))


async def update_projects(projects: list[Project]) -> StateModel:
    return await _mutate(lambda s: setattr(s, "projects", projects))


async def update_environments(environments: list[Environment]) -> StateModel:
    return await _mutate(lambda s: setattr(s, "environments", environments))


async def update_deployments(deployments: list[Deployment]) -> StateModel:
    return await _mutate(lambda s: setattr(s, "deployments", deployments))


async def update_settings(settings: AppSettings) -> StateModel:
    return await _mutate(lambda s: setattr(s, "settings", settings))


async def get_server(server_id: str) -> Server | None:
    state = await get_state()
    return next((s for s in state.servers if s.id == server_id), None)


async def get_project(project_id: str) -> Project | None:
    state = await get_state()
    return next((p for p in state.projects if p.id == project_id), None)


async def get_environment(environment_id: str) -> Environment | None:
    state = await get_state()
    return next((e for e in state.environments if e.id == environment_id), None)


async def get_deployment(deployment_id: str) -> Deployment | None:
    state = await get_state()
    return next((d for d in state.deployments if d.id == deployment_id), None)
