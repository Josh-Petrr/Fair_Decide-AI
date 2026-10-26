"""Server-Sent Events: push live updates (assignments, emails) to every open browser tab."""
import asyncio
import json

_subscribers: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop):
    global _loop
    _loop = loop


def publish(event: str, data: dict):
    """Safe to call from any thread (e.g. the email worker)."""
    if _loop is None:
        return
    msg = f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
    for q in list(_subscribers):
        _loop.call_soon_threadsafe(q.put_nowait, msg)


async def stream():
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)
    try:
        yield "event: hello\ndata: {}\n\n"
        while True:
            try:
                yield await asyncio.wait_for(q.get(), timeout=20)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        _subscribers.discard(q)
