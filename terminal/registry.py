"""
registry.py
-----------
Central catalogue of all 12 analysis agents. This is the single place
that knows about every agent — a future FastAPI layer (or any other
consumer) imports from here rather than reaching into agents/ directly,
so adding a 13th agent later only means: one new prompt .txt file, one
new agent .py file, and one new entry here.
"""

import asyncio

from .response_style import RESPONSE_STYLES, DEFAULT_RESPONSE_STYLE
from .agents.income_statement_agent import income_statement_agent, income_statement_agent_stream
from .agents.balance_sheet_agent import balance_sheet_agent, balance_sheet_agent_stream
from .agents.cash_flow_agent import cash_flow_agent, cash_flow_agent_stream
from .agents.liquidity_agent import liquidity_agent, liquidity_agent_stream
from .agents.solvency_agent import solvency_agent, solvency_agent_stream
from .agents.profitability_agent import profitability_agent, profitability_agent_stream
from .agents.valuation_agent import valuation_agent, valuation_agent_stream
from .agents.dcf_agent import dcf_agent, dcf_agent_stream
from .agents.growth_agent import growth_agent, growth_agent_stream
from .agents.volatility_agent import volatility_agent, volatility_agent_stream
from .agents.sentiment_agent import sentiment_agent, sentiment_agent_stream
from .agents.competitive_benchmarking_agent import (
    competitive_benchmarking_agent,
    competitive_benchmarking_agent_stream,
)


ANALYSIS_CATALOGUE = {
    "income_statement": {
        "function": income_statement_agent,
        "stream_function": income_statement_agent_stream,
        "description": "Multi-year P&L analysis: revenue, margins, EPS, earnings quality",
        "tools": ["resolve_ticker_symbol", "get_income_statement"],
    },
    "balance_sheet": {
        "function": balance_sheet_agent,
        "stream_function": balance_sheet_agent_stream,
        "description": "Asset composition, leverage, working capital, equity quality",
        "tools": ["resolve_ticker_symbol", "get_balance_sheet"],
    },
    "cash_flow": {
        "function": cash_flow_agent,
        "stream_function": cash_flow_agent_stream,
        "description": "OCF, FCF, CapEx, SBC, capital allocation quality",
        "tools": ["resolve_ticker_symbol", "get_cash_flow"],
    },
    "liquidity": {
        "function": liquidity_agent,
        "stream_function": liquidity_agent_stream,
        "description": "Current/Quick/Cash ratios, working capital, short-term risk",
        "tools": ["resolve_ticker_symbol", "get_balance_sheet", "get_key_metrics"],
    },
    "solvency": {
        "function": solvency_agent,
        "stream_function": solvency_agent_stream,
        "description": "Leverage, interest coverage, debt maturity, capital structure",
        "tools": ["resolve_ticker_symbol", "get_balance_sheet", "get_income_statement", "get_key_metrics"],
    },
    "profitability": {
        "function": profitability_agent,
        "stream_function": profitability_agent_stream,
        "description": "ROE, ROA, ROIC, DuPont decomposition, all margin layers",
        "tools": ["resolve_ticker_symbol", "get_income_statement", "get_balance_sheet", "get_key_metrics"],
    },
    "valuation": {
        "function": valuation_agent,
        "stream_function": valuation_agent_stream,
        "description": "P/E, EV/EBITDA, PEG, P/B, P/S, peer comparison, price position",
        "tools": ["resolve_ticker_symbol", "get_key_metrics", "get_company_overview", "get_stock_quote", "get_stock_peers"],
    },
    "dcf": {
        "function": dcf_agent,
        "stream_function": dcf_agent_stream,
        "description": "Intrinsic value via DCF: WACC, 3 scenarios, terminal value, per-share equity value",
        "tools": ["resolve_ticker_symbol", "get_cash_flow", "get_income_statement", "get_key_metrics", "get_company_overview"],
    },
    "growth": {
        "function": growth_agent,
        "stream_function": growth_agent_stream,
        "description": "Revenue/EPS CAGR, margin trajectory, Rule of 40, growth score",
        "tools": ["resolve_ticker_symbol", "get_income_statement", "get_key_metrics"],
    },
    "volatility": {
        "function": volatility_agent,
        "stream_function": volatility_agent_stream,
        "description": "Annualized volatility, Beta, Sharpe ratio, ATR, trend analysis",
        "tools": ["resolve_ticker_symbol", "get_price_history", "get_stock_quote", "get_key_metrics"],
    },
    "sentiment": {
        "function": sentiment_agent,
        "stream_function": sentiment_agent_stream,
        "description": "Short interest, ownership structure, news sentiment, squeeze risk",
        "tools": ["resolve_ticker_symbol", "get_share_statistics", "get_company_overview", "tavily"],
    },
    "competitive_benchmarking": {
        "function": competitive_benchmarking_agent,
        "stream_function": competitive_benchmarking_agent_stream,
        "description": "Peer market cap ranking, relative valuation, positioning matrix",
        "tools": ["resolve_ticker_symbol", "get_stock_peers", "get_key_metrics", "get_company_overview"],
    },
}


def list_analyses():
    """Print all available analyses with descriptions."""
    print("\n" + "="*65)
    print("  STOCKAGENT — AVAILABLE ANALYSES")
    print("="*65)
    for key, val in ANALYSIS_CATALOGUE.items():
        print(f"\n  [{key}]")
        print(f"  {val['description']}")
    print("\n" + "="*65 + "\n")


async def run_analysis(analysis_type: str, company_input: str,
                        response_style: str = DEFAULT_RESPONSE_STYLE) -> str:
    """
    Run any analysis by name, non-streaming — returns the final text.

    Args:
        response_style: "precise" | "balanced" | "exploratory".

    Example:
        result = await run_analysis("dcf", "Tesla", response_style="precise")
    """
    if analysis_type not in ANALYSIS_CATALOGUE:
        available = ", ".join(ANALYSIS_CATALOGUE.keys())
        return f"Unknown analysis type '{analysis_type}'. Available: {available}"
    fn = ANALYSIS_CATALOGUE[analysis_type]["function"]
    return await fn(company_input, response_style)


def run_analysis_stream(analysis_type: str, company_input: str,
                         response_style: str = DEFAULT_RESPONSE_STYLE):
    """
    Run any analysis by name, streaming — returns an async generator of
    event dicts (tool_start, tool_end, retry, token, done, failed).

    Args:
        response_style: "precise" | "balanced" | "exploratory".

    Example:
        async for event in run_analysis_stream("dcf", "Tesla", response_style="exploratory"):
            ...
    """
    if analysis_type not in ANALYSIS_CATALOGUE:
        available = ", ".join(ANALYSIS_CATALOGUE.keys())

        async def _error_gen():
            yield {"type": "failed", "content": f"Unknown analysis type '{analysis_type}'. Available: {available}"}

        return _error_gen()
    stream_fn = ANALYSIS_CATALOGUE[analysis_type]["stream_function"]
    return stream_fn(company_input, response_style)


# ═══════════════════════════════════════════════════════════════════
# TERMINAL DEMO
# One example consumer of run_analysis_stream() — prints tool-call
# events as they happen, then the report tokens as they're written.
# A FastAPI SSE/WebSocket endpoint would consume the same generator
# instead, forwarding each `event` dict to the browser.
# ═══════════════════════════════════════════════════════════════════

async def main():
    list_analyses()
    print("Type 'exit' or 'quit' at any prompt to stop.\n")
    print(f"Response styles available: {', '.join(RESPONSE_STYLES.keys())} "
          f"(press Enter for default: {DEFAULT_RESPONSE_STYLE})\n")

    while True:
        analysis_type = input("Which analysis would you like to run? ").strip().lower()
        if analysis_type in ("exit", "quit"):
            print("Goodbye!")
            break

        company_input = input("Company name or ticker symbol: ").strip()
        if company_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        response_style = input(
            f"Response style [{'/'.join(RESPONSE_STYLES.keys())}] "
            f"(Enter for {DEFAULT_RESPONSE_STYLE}): "
        ).strip().lower() or DEFAULT_RESPONSE_STYLE

        if analysis_type not in ANALYSIS_CATALOGUE:
            print(f"\n'{analysis_type}' is not a recognized analysis type. "
                  f"Choose one of: {', '.join(ANALYSIS_CATALOGUE.keys())}\n")
            continue

        print(f"\n▶ Running {analysis_type} analysis for {company_input} "
              f"(style: {response_style})...\n")

        async for event in run_analysis_stream(analysis_type, company_input, response_style):
            etype = event["type"]

            if etype == "tool_start":
                print(f"🔧 Calling {event['tool']}...")

            elif etype == "tool_end":
                print(f"✓ {event['tool']} completed.")

            elif etype == "retry":
                print(f"🔁 Retrying... (attempt {event['attempt']}/{event['max_retries']})")

            elif etype == "token":
                print(event["content"], end="", flush=True)

            elif etype == "failed":
                print(f"\n⚠ {event['content']}")

            elif etype == "done":
                print()  # final newline once the streamed report finishes

        print("\n" + "─"*65)
        print("Ready for another analysis.\n")


if __name__ == "__main__":
    asyncio.run(main())
