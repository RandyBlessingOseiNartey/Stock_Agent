"""
income_statement_agent.py
--------------------------
Multi-year income statement and earnings quality analysis.
Tools: resolve_ticker_symbol, get_income_statement
"""

from ..tool_set.terminal_tools import resolve_ticker_symbol, get_income_statement
from .shared import load_prompt, run_agent_stream, run_agent

AGENT_NAME = "income_statement_agent"
PROMPT = load_prompt("income_statement.txt")
TOOLS = [resolve_ticker_symbol, get_income_statement]


async def income_statement_agent_stream(company_input: str, response_style: str):
    """Streaming version — yields tool-call events, then live tokens."""
    async for event in run_agent_stream(AGENT_NAME, TOOLS, PROMPT, company_input, response_style):
        yield event


async def income_statement_agent(company_input: str) -> str:
    """Non-streaming convenience version — returns the final report text."""
    return await run_agent(AGENT_NAME, TOOLS, PROMPT, company_input)