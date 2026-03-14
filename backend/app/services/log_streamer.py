import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from app.models.state import LogLine

_subscribers: dict[str, list[asyncio.Queue]] = {}
_history: dict[str, list[LogLine]] = {}


def _make(deployment_id: str, stage: str, message: str, level: str = "info") -> LogLine:
    return LogLine(
        deployment_id=deployment_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        stage=stage,
        level=level,
        message=message,
    )


async def publish(deployment_id: str, line: LogLine) -> None:
    _history.setdefault(deployment_id, []).append(line)
    for q in _subscribers.get(deployment_id, []):
        await q.put(line)


async def emit(deployment_id: str, stage: str, message: str, level: str = "info") -> None:
    await publish(deployment_id, _make(deployment_id, stage, message, level))


async def subscribe(deployment_id: str) -> AsyncGenerator[LogLine, None]:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(deployment_id, []).append(q)
    for line in _history.get(deployment_id, []):
        yield line
    try:
        while True:
            try:
                line = await asyncio.wait_for(q.get(), timeout=25.0)
                if line is None:
                    break
                yield line
            except asyncio.TimeoutError:
                yield _make(deployment_id, "keepalive", "", "info")
    finally:
        try:
            _subscribers[deployment_id].remove(q)
        except (KeyError, ValueError):
            pass


async def close_stream(deployment_id: str) -> None:
    for q in _subscribers.get(deployment_id, []):
        await q.put(None)


def get_history(deployment_id: str) -> list[LogLine]:
    return _history.get(deployment_id, [])
