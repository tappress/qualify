import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from qualify.routers import servers, projects, environments, deployments, logs, settings as settings_router
from qualify.services.state_manager import get_state

# When frozen by PyInstaller, bundled files are in sys._MEIPASS.
# In dev, the frontend is served by the Vite dev server (port 65432) instead.
if getattr(sys, "frozen", False):
    _BASE = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    STATIC_DIR: Path | None = _BASE / "frontend" / "dist"
else:
    STATIC_DIR = None  # dev mode: Vite handles the frontend


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_state()
    yield


app = FastAPI(title="Qualify API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:65432"],
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


# Serve bundled frontend in production (frozen binary only)
if STATIC_DIR and STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(STATIC_DIR / "index.html")
