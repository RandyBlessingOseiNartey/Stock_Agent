"""
cash_flow_agent.py
--------------------
Operating/free cash flow, CapEx, and capital allocation quality analysis.
Tools: resolve_ticker_symbol, get_cash_flow
"""

from ..tool_set.terminal_tools import resolve_ticker_symbol, get_cash_flow
from .shared import load_prompt, run_agent_stream, run_agent

AGENT_NAME = "cash_flow_agent"
PROMPT = load_prompt("cash_flow.txt")
TOOLS = [resolve_ticker_symbol, get_cash_flow]


async def cash_flow_agent_stream(company_input: str, response_style: str):
    """Streaming version — yields tool-call events, then live tokens."""
    async for event in run_agent_stream(AGENT_NAME, TOOLS, PROMPT, company_input, response_style):
        yield event


async def cash_flow_agent(company_input: str) -> str:
    """Non-streaming convenience version — returns the final report text."""
    return await run_agent(AGENT_NAME, TOOLS, PROMPT, company_input)