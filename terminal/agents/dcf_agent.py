"""
dcf_agent.py
--------------
Intrinsic value via DCF: WACC, Bear/Base/Bull FCF projections, terminal
value, and per-share equity value.
Tools: resolve_ticker_symbol, get_cash_flow, get_income_statement,
       get_key_metrics, get_company_overview
"""

from ..tool_set.terminal_tools import (
    resolve_ticker_symbol,
    get_cash_flow,
    get_income_statement,
    get_key_metrics,
    get_company_overview,
)
from .shared import load_prompt, run_agent_stream, run_agent

AGENT_NAME = "dcf_agent"
PROMPT = load_prompt("dcf.txt")
TOOLS = [resolve_ticker_symbol, get_cash_flow, get_income_statement, get_key_metrics, get_company_overview]


async def dcf_agent_stream(company_input: str, response_style: str):
    """Streaming version — yields tool-call events, then live tokens."""
    async for event in run_agent_stream(AGENT_NAME, TOOLS, PROMPT, company_input, response_style):
        yield event


async def dcf_agent(company_input: str) -> str:
    """Non-streaming convenience version — returns the final report text."""
    return await run_agent(AGENT_NAME, TOOLS, PROMPT, company_input)