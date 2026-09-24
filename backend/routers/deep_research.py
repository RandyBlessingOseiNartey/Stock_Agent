from fastapi import APIRouter
from pydantic import BaseModel

from deep_research.agent import run_pipeline_stream

from ..sse import stream_events

router = APIRouter(prefix="/api/deep-research", tags=["deep-research"])


class DeepResearchRequest(BaseModel):
    query: str
    response_style: str = "balanced"
    risk_appetite: str = "moderate"


@router.post("/stream")
async def stream_deep_research(payload: DeepResearchRequest):
    return stream_events(
        run_pipeline_stream(
            payload.query, payload.response_style, payload.risk_appetite
        )
    )
