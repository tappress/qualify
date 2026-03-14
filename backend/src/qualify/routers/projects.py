from fastapi import APIRouter, HTTPException
from qualify.models.state import Deployment, EnvParseRequest, InfraInference, Project, ProjectCreate, ProjectUpdate
from qualify.services import state_manager
from qualify.services.env_parser import parse_env_template

router = APIRouter()


@router.get("/", response_model=list[Project])
async def list_projects():
    state = await state_manager.get_state()
    return state.projects


@router.post("/", response_model=Project, status_code=201)
async def create_project(body: ProjectCreate):
    state = await state_manager.get_state()
    project = Project(**body.model_dump())
    if project.env_template_content:
        project.inferred_infra = parse_env_template(project.env_template_content)
    state.projects.append(project)
    await state_manager.update_projects(state.projects)
    return project


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str):
    project = await state_manager.get_project(project_id)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    return project


@router.put("/{project_id}", response_model=Project)
async def update_project(project_id: str, body: ProjectUpdate):
    state = await state_manager.get_state()
    project = next((p for p in state.projects if p.id == project_id), None)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(project, field, val)
    if body.env_template_content is not None:
        project.inferred_infra = parse_env_template(body.env_template_content)
    await state_manager.update_projects(state.projects)
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    state = await state_manager.get_state()
    before = len(state.projects)
    state.projects = [p for p in state.projects if p.id != project_id]
    if len(state.projects) == before:
        raise HTTPException(404, f"Project {project_id} not found")
    await state_manager.update_projects(state.projects)
    return {"ok": True}


@router.post("/{project_id}/parse-env", response_model=InfraInference)
async def parse_env(project_id: str, body: EnvParseRequest):
    if not await state_manager.get_project(project_id):
        raise HTTPException(404, f"Project {project_id} not found")
    return parse_env_template(body.content)


@router.get("/{project_id}/deployments", response_model=list[Deployment])
async def project_deployments(project_id: str):
    state = await state_manager.get_state()
    return [d for d in state.deployments if d.project_id == project_id]
