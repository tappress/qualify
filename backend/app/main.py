from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import servers, projects, environments, deployments, logs, settings as settings_router
from app.services.state_manager import get_state


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

app.include_router(servers.router,          prefix="/api/servers",                        tags=["servers"])
app.include_router(projects.router,         prefix="/api/projects",                       tags=["projects"])
app.include_router(environments.router,     prefix="/api/projects/{project_id}/envs",     tags=["environments"])
app.include_router(deployments.router,      prefix="/api/deployments",                    tags=["deployments"])
app.include_router(logs.router,             prefix="/api",                                tags=["logs"])
app.include_router(settings_router.router,  prefix="/api/settings",                       tags=["settings"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=65444, reload=True)
