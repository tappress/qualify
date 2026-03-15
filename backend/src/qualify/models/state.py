from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
import uuid_utils


def _uid() -> str:
    return str(uuid_utils.uuid7())


# ── Shared ────────────────────────────────────────────────────────────────────

class CheckResult(BaseModel):
    check: str
    status: Literal["pass", "fail", "warn", "skip"]
    message: str
    details: Optional[dict] = None


# ── Settings ──────────────────────────────────────────────────────────────────

class RegistryConfig(BaseModel):
    url: str = ""
    username: str = ""


class AppSettings(BaseModel):
    primary_server_id: Optional[str] = None
    registry: RegistryConfig = Field(default_factory=RegistryConfig)
    # Actual token stored in OS keyring under "qualify:cloudflare_token"
    cloudflare_token_stored: bool = False
    cloudflare_zone_id: str = ""


# ── Server ────────────────────────────────────────────────────────────────────

class Server(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    host: str
    port: int = 22
    user: str
    ssh_key_path: Optional[str] = None
    auth_method: Optional[Literal["key", "password"]] = None  # detected on first successful connect
    # sudo password stored in OS keyring under "qualify:{id}:sudo"
    tags: list[str] = []
    public_ip: Optional[str] = None  # detected during qualify
    status: Literal["unknown", "bootstrapping", "bootstrap_failed", "qualified", "failed", "qualifying"] = "unknown"
    bootstrapped_at: Optional[datetime] = None
    os_id: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    last_qualified_at: Optional[datetime] = None
    qualify_results: list[CheckResult] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ServerCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    user: str
    ssh_key_path: Optional[str] = None
    sudo_password: Optional[str] = None  # sent once, stored in keyring, never persisted
    tags: list[str] = []


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    ssh_key_path: Optional[str] = None
    sudo_password: Optional[str] = None
    tags: Optional[list[str]] = None


# ── Environment ───────────────────────────────────────────────────────────────

class EnvVarRef(BaseModel):
    key: str
    value: str = ""           # non-secret value stored locally
    is_secret: bool = False   # if True, value is empty here
    secret_name: str = ""     # Docker Secret name on the server, e.g. "qualify_myapp_dev_DATABASE_URL"


class InfraInference(BaseModel):
    postgres: bool = False
    redis: bool = False
    traefik: bool = True
    minio: bool = False
    custom_services: list[str] = []


class EnvVarCheck(BaseModel):
    """Result of pre-flight env var validation."""
    key: str
    status: Literal["provided", "will_provision", "missing"]
    note: str = ""


class Environment(BaseModel):
    id: str = Field(default_factory=_uid)
    project_id: str
    name: str                           # "dev", "staging", "prod", etc.
    server_id: str
    domain: str = ""
    port: int = 3000
    env_vars: list[EnvVarRef] = []
    inferred_infra: InfraInference = Field(default_factory=InfraInference)
    # DNS: if None, user manages DNS manually; if set, was auto-created via Cloudflare
    cloudflare_record_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EnvironmentCreate(BaseModel):
    name: str
    server_id: str
    domain: str = ""
    port: int = 3000
    env_vars: list[EnvVarRef] = []
    auto_dns: bool = False   # attempt Cloudflare DNS creation if token is stored


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = None
    server_id: Optional[str] = None
    domain: Optional[str] = None
    port: Optional[int] = None
    env_vars: Optional[list[EnvVarRef]] = None


# ── Project ───────────────────────────────────────────────────────────────────

class Project(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    git_url: str
    git_branch: str = "main"
    build_context: str = "."
    dockerfile_path: str = "Dockerfile"
    env_template_content: str = ""      # contents of .env.template / .env.example
    build_strategy: Literal["local", "remote"] = "local"
    image_name: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectCreate(BaseModel):
    name: str
    git_url: str
    git_branch: str = "main"
    build_context: str = "."
    dockerfile_path: str = "Dockerfile"
    env_template_content: str = ""
    build_strategy: Literal["local", "remote"] = "local"
    image_name: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    git_url: Optional[str] = None
    git_branch: Optional[str] = None
    build_context: Optional[str] = None
    dockerfile_path: Optional[str] = None
    env_template_content: Optional[str] = None
    build_strategy: Optional[Literal["local", "remote"]] = None
    image_name: Optional[str] = None


# ── Deployment ────────────────────────────────────────────────────────────────

class DeploymentStage(BaseModel):
    name: str
    status: Literal["pending", "running", "success", "failed", "skipped"] = "pending"
    duration_ms: Optional[int] = None


class Deployment(BaseModel):
    id: str = Field(default_factory=_uid)
    project_id: str
    environment_id: str
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: Literal["pending", "running", "success", "failed", "cancelled"] = "pending"
    image_tag: Optional[str] = None
    git_sha: Optional[str] = None
    build_strategy: Literal["local", "remote"] = "local"
    stages: list[DeploymentStage] = []
    error: Optional[str] = None


class DeploymentRequest(BaseModel):
    project_id: str
    environment_id: str
    build_strategy: Optional[Literal["local", "remote"]] = None


# ── Logs ──────────────────────────────────────────────────────────────────────

class LogLine(BaseModel):
    deployment_id: str
    timestamp: str
    stage: str
    level: Literal["info", "warn", "error"] = "info"
    message: str


# ── API misc ──────────────────────────────────────────────────────────────────

class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None


class EnvParseRequest(BaseModel):
    content: str


class SettingsUpdate(BaseModel):
    primary_server_id: Optional[str] = None
    registry: Optional[RegistryConfig] = None
    cloudflare_token: Optional[str] = None   # sent once, stored in keyring
    cloudflare_zone_id: Optional[str] = None


# ── Root state ────────────────────────────────────────────────────────────────

class StateModel(BaseModel):
    version: str = "1"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    settings: AppSettings = Field(default_factory=AppSettings)
    servers: list[Server] = []
    projects: list[Project] = []
    environments: list[Environment] = []
    deployments: list[Deployment] = []
