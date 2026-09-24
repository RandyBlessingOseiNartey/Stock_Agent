"""
solvency_agent.py
--------------------
Leverage, interest coverage, debt maturity, capital structure analysis.
Tools: resolve_ticker_symbol, get_balance_sheet, get_income_statement, get_key_metrics
"""

from ..tool_set.terminal_tools import (
    resolve_ticker_symbol,
    get_balance_sheet,
    get_income_statement,
    get_key_metrics,
)
from .shared import load_prompt, run_agent_stream, run_agent

AGENT_NAME = "solvency_agent"
PROMPT = load_prompt("solvency.txt")
TOOLS = [resolve_ticker_symbol, get_balance_sheet, get_income_statement, get_key_metrics]


async def solvency_agent_stream(company_input: str, response_style: str):
    """Streaming version — yields tool-call events, then live tokens."""
    async for event in run_agent_stream(AGENT_NAME, TOOLS, PROMPT, company_input, response_style):
        yield event


async def solvency_agent(company_input: str) -> str:
    """Non-streaming convenience version — returns the final report text."""
    return await run_agent(AGENT_NAME, TOOLS, PROMPT, company_input)