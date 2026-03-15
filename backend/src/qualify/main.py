import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from qualify.routers import servers, projects, environments, deployments, logs, settings as settings_router
from qualify.services import state_manager
from qualify.services.state_manager import get_state
from qualify.services.auth import verify_token

# When frozen by PyInstaller, bundled files are in sys._MEIPASS.
# In dev, the frontend is served by the Vite dev server (port 65432) instead.
if getattr(sys, "frozen", False):
    _BASE = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    STATIC_DIR: Path | None = _BASE / "frontend" / "dist"
else:
    STATIC_DIR = None  # dev mode: Vite handles the frontend


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = await state_manager.get_state()
    # Transient statuses ("bootstrapping", "qualifying") mean an operation was
    # in-flight when the server last stopped. Reset them so the UI isn't stuck.
    changed = False
    for server in state.servers:
        if server.status in ("bootstrapping", "qualifying"):
            server.status = "unknown"
            changed = True
    for dep in state.deployments:
        if dep.status == "running":
            dep.status = "failed"
            dep.error = "Interrupted by server restart"
            changed = True
    if changed:
        await state_manager.update_servers(state.servers)
        await state_manager.update_deployments(state.deployments)
    yield


app = FastAPI(title="Qualify API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Only enforce auth in the frozen binary (production). In dev mode
    # (make dev / uvicorn --reload) auth is skipped for convenience.
    if getattr(sys, "frozen", False) and request.url.path.startswith("/api"):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        # Fall back to ?token= query param for SSE (EventSource can't set headers)
        if not token:
            token = request.query_params.get("token", "")
        if not verify_token(token):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(servers.router,          prefix="/api/servers",                    tags=["servers"])
app.include_router(projects.router,         prefix="/api/projects",                   tags=["projects"])
app.include_router(environments.router,     prefix="/api/projects/{project_id}/envs", tags=["environments"])
app.include_router(deployments.router,      prefix="/api/deployments",                tags=["deployments"])
app.include_router(logs.router,             prefix="/api",                            tags=["logs"])
app.include_router(settings_router.router,  prefix="/api/settings",                   tags=["settings"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/environments")
async def list_all_environments():
    """Flat list of all environments across all projects (used by server detail view)."""
    state = await get_state()
    return state.environments


# Serve bundled frontend in production (frozen binary only)
if STATIC_DIR and STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(STATIC_DIR / "index.html")
