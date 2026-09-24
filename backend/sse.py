"""
sse.py
------
One shared wrapper around EventSourceResponse, used by all three stream
routers so the disconnect handling, proxy headers, and terminal-event
guarantee are defined once instead of three times.
"""

import json
from collections.abc import AsyncIterator

from sse_starlette.sse import EventSourceResponse

# Without these, nginx and friends buffer the response and the client
# sees nothing until the whole run finishes — which defeats streaming.
_NO_BUFFER_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def stream_events(source: AsyncIterator[dict]) -> EventSourceResponse:
    """
    Forwards each event dict from a feature pipeline verbatim as one SSE
    message.

    The pipelines already handle their own errors internally and yield a
    "failed" event once retries are exhausted. The try/except here is
    defense in depth for anything truly unexpected (a bug, an OOM, an
    unhandled provider exception) so the connection always ends on a
    clean terminal event rather than dying silently mid-stream.
    """

    async def event_generator():
        try:
            async for event in source:
                yield {"data": json.dumps(event)}
        except Exception as e:
            yield {
                "data": json.dumps(
                    {"type": "failed", "content": f"Unexpected server error: {e}"}
                )
            }

    return EventSourceResponse(event_generator(), headers=_NO_BUFFER_HEADERS)
