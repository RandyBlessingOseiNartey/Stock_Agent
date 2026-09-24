"""
competitive_benchmarking_agent.py
------------------------------------
Peer market cap ranking, relative valuation, and competitive positioning matrix.
Tools: resolve_ticker_symbol, get_stock_peers, get_key_metrics, get_company_overview
"""

from ..tool_set.terminal_tools import (
    resolve_ticker_symbol,
    get_stock_peers,
    get_key_metrics,
    get_company_overview,
)
from .shared import load_prompt, run_agent_stream, run_agent

AGENT_NAME = "competitive_benchmarking_agent"
PROMPT = load_prompt("competitive_benchmarking.txt")
TOOLS = [resolve_ticker_symbol, get_stock_peers, get_key_metrics, get_company_overview]


async def competitive_benchmarking_agent_stream(company_input: str, response_style: str):
    """Streaming version — yields tool-call events, then live tokens."""
    async for event in run_agent_stream(AGENT_NAME, TOOLS, PROMPT, company_input, response_style):
        yield event


async def competitive_benchmarking_agent(company_input: str) -> str:
    """Non-streaming convenience version — returns the final report text."""
    return await run_agent(AGENT_NAME, TOOLS, PROMPT, company_input)