import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

log = logging.getLogger(__name__)
from qualify.models.state import CheckResult, ConnectionTestResult, Server, ServerCreate, ServerUpdate
from qualify.services import preflight, ssh_client, state_manager
from qualify.services.keyring_store import delete_sudo_password, get_sudo_password, store_sudo_password
from qualify.services.provisioner import UnsupportedOSError, detect_os, get_provisioner
from qualify.services import server_audit

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
        public_ip=body.host,
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

    raw_conn, _ = await ssh_client.get_connection(server)
    conn = server_audit.AuditedConn(raw_conn, stage="bootstrap", sudo_password=get_sudo_password(server.id))
    os_info = None
    try:
        os_info = await detect_os(conn)
        server.os_id = os_info.id
        server.os_name = os_info.name
        server.os_version = os_info.version
        await state_manager.update_servers(state.servers)
        provisioner = get_provisioner(os_info)
        await provisioner.bootstrap(conn, advertise_addr=server.host, ssh_port=server.port)
        server.status = "unknown"  # ready for qualify
        server.bootstrapped_at = datetime.now(timezone.utc)
    except UnsupportedOSError as e:
        server.status = "bootstrap_failed"
        server.last_error = str(e)
        await state_manager.update_servers(state.servers)
        raise HTTPException(422, str(e))
    except Exception as e:
        log.exception("Bootstrap failed for server %s", server_id)
        stderr = getattr(e, "stderr", None)
        detail = f"{e}\n{stderr}".strip() if stderr else str(e)
        server.status = "bootstrap_failed"
        server.last_error = detail
        await state_manager.update_servers(state.servers)
        raise HTTPException(500, detail)
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
    results = await preflight.run_preflight(server, audit_stage="preflight")
    server.qualify_results = results
    server.last_qualified_at = datetime.now(timezone.utc)
    server.status = "qualified" if all(r.status in ("pass", "warn", "skip") for r in results) else "failed"
    await state_manager.update_servers(state.servers)
    return results


@router.get("/{server_id}/audit-log")
async def get_audit_log(server_id: str):
    server = await state_manager.get_server(server_id)
    if not server:
        raise HTTPException(404, f"Server {server_id} not found")
    conn, _ = await ssh_client.get_connection(server)
    try:
        return await server_audit.fetch_log(conn)
    finally:
        conn.close()
