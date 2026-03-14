from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.models.state import Deployment, DeploymentRequest
from app.services import state_manager
from app.services.orchestrator import run_deployment

router = APIRouter()


@router.get("/", response_model=list[Deployment])
async def list_deployments():
    state = await state_manager.get_state()
    return sorted(state.deployments, key=lambda d: d.triggered_at, reverse=True)


@router.post("/", status_code=202)
async def trigger_deployment(body: DeploymentRequest, background_tasks: BackgroundTasks):
    state = await state_manager.get_state()

    project = next((p for p in state.projects if p.id == body.project_id), None)
    if not project:
        raise HTTPException(404, f"Project {body.project_id} not found")

    env = next((e for e in state.environments if e.id == body.environment_id), None)
    if not env:
        raise HTTPException(404, f"Environment {body.environment_id} not found")

    if env.project_id != project.id:
        raise HTTPException(400, "Environment does not belong to this project")

    server = next((s for s in state.servers if s.id == env.server_id), None)
    if not server:
        raise HTTPException(404, f"Server {env.server_id} not found")

    strategy = body.build_strategy or project.build_strategy
    deployment = Deployment(
        project_id=project.id,
        environment_id=env.id,
        build_strategy=strategy,
    )
    state.deployments.append(deployment)
    await state_manager.update_deployments(state.deployments)
    background_tasks.add_task(run_deployment, deployment.id, project, env, server, strategy)
    return {"id": deployment.id, "status": "pending"}


@router.get("/{deployment_id}", response_model=Deployment)
async def get_deployment(deployment_id: str):
    dep = await state_manager.get_deployment(deployment_id)
    if not dep:
        raise HTTPException(404, f"Deployment {deployment_id} not found")
    return dep


@router.post("/{deployment_id}/cancel")
async def cancel_deployment(deployment_id: str):
    state = await state_manager.get_state()
    dep = next((d for d in state.deployments if d.id == deployment_id), None)
    if not dep:
        raise HTTPException(404, f"Deployment {deployment_id} not found")
    if dep.status not in ("pending", "running"):
        raise HTTPException(400, f"Cannot cancel deployment with status '{dep.status}'")
    dep.status = "cancelled"
    await state_manager.update_deployments(state.deployments)
    return {"ok": True}
