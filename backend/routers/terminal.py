from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from terminal.registry import ANALYSIS_CATALOGUE, run_analysis_stream

from ..sse import stream_events

router = APIRouter(prefix="/api/terminal", tags=["terminal"])


class TerminalRequest(BaseModel):
    analysis_type: str
    company_input: str
    response_style: str = "balanced"


@router.get("/analyses")
async def list_analyses():
    return [
        {"key": key, "description": val["description"], "tools": val["tools"]}
        for key, val in ANALYSIS_CATALOGUE.items()
    ]


@router.post("/stream")
async def stream_terminal(payload: TerminalRequest):
    # The one input worth rejecting up front: an unknown analysis_type
    # would otherwise surface as an in-stream "failed" event, which reads
    # to the client like a pipeline failure rather than a bad request.
    if payload.analysis_type not in ANALYSIS_CATALOGUE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown analysis_type '{payload.analysis_type}'. "
                f"Valid options: {', '.join(ANALYSIS_CATALOGUE.keys())}"
            ),
        )

    return stream_events(
        run_analysis_stream(
            payload.analysis_type, payload.company_input, payload.response_style
        )
    )
