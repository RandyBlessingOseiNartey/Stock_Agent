"""
valuation_agent.py
---------------------
P/E, EV/EBITDA, PEG, P/B, P/S, and peer-relative valuation analysis.
Tools: resolve_ticker_symbol, get_key_metrics, get_company_overview,
       get_stock_quote, get_stock_peers
"""

from ..tool_set.terminal_tools import (
    resolve_ticker_symbol,
    get_key_metrics,
    get_company_overview,
    get_stock_quote,
    get_stock_peers,
)
from .shared import load_prompt, run_agent_stream, run_agent

AGENT_NAME = "valuation_agent"
PROMPT = load_prompt("valuation.txt")
TOOLS = [resolve_ticker_symbol, get_key_metrics, get_company_overview, get_stock_quote, get_stock_peers]


async def valuation_agent_stream(company_input: str, response_style: str):
    """Streaming version — yields tool-call events, then live tokens."""
    async for event in run_agent_stream(AGENT_NAME, TOOLS, PROMPT, company_input, response_style):
        yield event


async def valuation_agent(company_input: str) -> str:
    """Non-streaming convenience version — returns the final report text."""
    return await run_agent(AGENT_NAME, TOOLS, PROMPT, company_input)