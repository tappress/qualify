from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from qualify.models.state import CheckResult, ConnectionTestResult, Server, ServerCreate, ServerUpdate
from qualify.services import preflight, ssh_client, state_manager
from qualify.services.keyring_store import delete_sudo_password, store_sudo_password
from qualify.services.provisioner import UnsupportedOSError, detect_os, get_provisioner

router = APIRouter()


@router.get("/", response_model=list[Server])
async def list_servers():
    state = await state_manager.get_state()
    return state.servers


@router.post("/", response_model=Server, status_code=201)
async def create_server(body: ServerCreate):
    state = await state_manager.get_state()
    server = Server(
        name=body.name, host=body.host, port=body.port,
        user=body.user, ssh_key_path=body.ssh_key_path, tags=body.tags,
    )
    if body.sudo_password:
        store_sudo_password(server.id, body.sudo_password)
    state.servers.append(server)
    await state_manager.update_servers(state.servers)
    return server


@router.get("/{server_id}", response_model=Server)
async def get_server(server_id: str):
    server = await state_manager.get_server(server_id)
    if not server:
        raise HTTPException(404, f"Server {server_id} not found")
    return server


@router.put("/{server_id}", response_model=Server)
async def update_server(server_id: str, body: ServerUpdate):
    state = await state_manager.get_state()
    server = next((s for s in state.servers if s.id == server_id), None)
    if not server:
        raise HTTPException(404, f"Server {server_id} not found")
    for field, val in body.model_dump(exclude_none=True, exclude={"sudo_password"}).items():
        setattr(server, field, val)
    if body.sudo_password is not None:
        store_sudo_password(server_id, body.sudo_password)
    await state_manager.update_servers(state.servers)
    return server


@router.delete("/{server_id}")
async def delete_server(server_id: str):
    state = await state_manager.get_state()
    before = len(state.servers)
    state.servers = [s for s in state.servers if s.id != server_id]
    if len(state.servers) == before:
        raise HTTPException(404, f"Server {server_id} not found")
    delete_sudo_password(server_id)
    await state_manager.update_servers(state.servers)
    return {"ok": True}


@router.post("/{server_id}/test-connection", response_model=ConnectionTestResult)
async def test_connection(server_id: str):
    state = await state_manager.get_state()
    server = next((s for s in state.servers if s.id == server_id), None)
    if not server:
        raise HTTPException(404, f"Server {server_id} not found")
    ok, msg, latency, method = await ssh_client.test_connection(server)
    if ok and method and server.auth_method != method:
        server.auth_method = method
        await state_manager.update_servers(state.servers)
    return ConnectionTestResult(success=ok, message=msg, latency_ms=latency)


@router.post("/{server_id}/bootstrap")
async def bootstrap_server(server_id: str):
    state = await state_manager.get_state()
    server = next((s for s in state.servers if s.id == server_id), None)
    if not server:
        raise HTTPException(404, f"Server {server_id} not found")

    server.status = "bootstrapping"
    await state_manager.update_servers(state.servers)

    conn, _ = await ssh_client.get_connection(server)
    os_info = None
    try:
        os_info = await detect_os(conn)
        provisioner = get_provisioner(os_info)
        await provisioner.bootstrap(conn)
        server.status = "unknown"  # ready for qualify
        server.bootstrapped_at = datetime.now(timezone.utc)
        server.os_id = os_info.id
        server.os_name = os_info.name
        server.os_version = os_info.version
    except UnsupportedOSError as e:
        server.status = "bootstrap_failed"
        await state_manager.update_servers(state.servers)
        raise HTTPException(422, str(e))
    except Exception as e:
        server.status = "bootstrap_failed"
        await state_manager.update_servers(state.servers)
        raise HTTPException(500, str(e))
    finally:
        conn.close()

    await state_manager.update_servers(state.servers)
    return {"ok": True, "os": os_info.model_dump()}


@router.post("/{server_id}/qualify", response_model=list[CheckResult])
async def qualify_server(server_id: str):
    state = await state_manager.get_state()
    server = next((s for s in state.servers if s.id == server_id), None)
    if not server:
        raise HTTPException(404, f"Server {server_id} not found")
    server.status = "qualifying"
    await state_manager.update_servers(state.servers)
    results = await preflight.run_preflight(server)
    server.qualify_results = results
    server.last_qualified_at = datetime.now(timezone.utc)
    server.status = "qualified" if all(r.status in ("pass", "warn", "skip") for r in results) else "failed"
    await state_manager.update_servers(state.servers)
    return results
