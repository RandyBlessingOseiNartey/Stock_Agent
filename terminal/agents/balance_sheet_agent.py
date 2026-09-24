"""
balance_sheet_agent.py
------------------------
Asset composition, leverage, working capital, and equity quality analysis.
Tools: resolve_ticker_symbol, get_balance_sheet
"""

from ..tool_set.terminal_tools import resolve_ticker_symbol, get_balance_sheet
from .shared import load_prompt, run_agent_stream, run_agent

AGENT_NAME = "balance_sheet_agent"
PROMPT = load_prompt("balance_sheet.txt")
TOOLS = [resolve_ticker_symbol, get_balance_sheet]


async def balance_sheet_agent_stream(company_input: str, response_style: str):
    """Streaming version — yields tool-call events, then live tokens."""
    async for event in run_agent_stream(AGENT_NAME, TOOLS, PROMPT, company_input, response_style):
        yield event


async def balance_sheet_agent(company_input: str) -> str:
    """Non-streaming convenience version — returns the final report text."""
    return await run_agent(AGENT_NAME, TOOLS, PROMPT, company_input)