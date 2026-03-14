from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from qualify.models.state import LogLine
from qualify.services import log_streamer

router = APIRouter()


@router.get("/logs/stream/{deployment_id}")
async def stream_logs(deployment_id: str):
    async def generate():
        async for line in log_streamer.subscribe(deployment_id):
            if line.message:
                yield f"data: {line.model_dump_json()}\n\n"
            else:
                yield ": keepalive\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/logs/history/{deployment_id}", response_model=list[LogLine])
async def log_history(deployment_id: str):
    return log_streamer.get_history(deployment_id)
