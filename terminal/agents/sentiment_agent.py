"""
sentiment_agent.py
---------------------
Short interest, ownership structure, squeeze risk, and news sentiment analysis.
Tools: resolve_ticker_symbol, get_share_statistics, get_company_overview, tavily
"""

from ..tool_set.terminal_tools import (
    resolve_ticker_symbol,
    get_share_statistics,
    get_company_overview,
    tavily,
)
from .shared import load_prompt, run_agent_stream, run_agent

AGENT_NAME = "sentiment_agent"
PROMPT = load_prompt("sentiment.txt")
TOOLS = [resolve_ticker_symbol, get_share_statistics, get_company_overview, tavily]


async def sentiment_agent_stream(company_input: str, response_style: str):
    """Streaming version — yields tool-call events, then live tokens."""
    async for event in run_agent_stream(AGENT_NAME, TOOLS, PROMPT, company_input, response_style):
        yield event


async def sentiment_agent(company_input: str) -> str:
    """Non-streaming convenience version — returns the final report text."""
    return await run_agent(AGENT_NAME, TOOLS, PROMPT, company_input)