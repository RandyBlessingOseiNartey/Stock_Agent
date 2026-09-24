import asyncio
from datetime import date, datetime
from openbb import obb
from .config import config
from langchain.tools import tool
from .peers_agent import peers_agent
from .tavily_search_tool import tavily_search

obb.user.defaults.commands = config["defaults"]["commands"]


def _json_safe(obj):
    """
    Recursively converts date/datetime objects to ISO-format strings
    throughout a nested dict/list structure.

    Why this exists: OpenBB's raw results embed real datetime.date
    objects (e.g. period_ending: datetime.date(2025, 12, 31)). When
    LangChain stringifies a tool's return value for the LLM, a raw
    date object serializes as Python repr text, not valid JSON — which
    quietly conflicts with every system prompt's "output strictly
    valid JSON" instruction. Applying this once, in _to_dict, fixes it
    at the source for every tool that flows through it.
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


def _to_dict(result):
    """
    Converts an OpenBB OBBject result to a plain, JSON-safe dict/list
    the agent can read and that can be safely handed off as chart data.
    Falls back gracefully if conversion fails.

    Left as a plain sync function on purpose — it does no I/O at all,
    it only reshapes data already sitting in memory, so there is nothing
    for asyncio to help with here.
    """
    try:
        df = result.to_dataframe()
        return _json_safe(df.to_dict(orient="records"))
    except Exception:
        try:
            return _json_safe([r.model_dump() for r in result.results])
        except Exception:
            return str(result)


@tool
async def resolve_ticker_symbol(company_name: str):
    """
    Use this tool to find the correct stock ticker symbol for a company by name.

    This is the first tool to call when a user provides a company name instead
    of a ticker symbol. It searches the SEC and Yahoo Finance databases for
    matching companies and returns their ticker symbols, exchange, and CIK number.

    Returns multiple matches — the most relevant result is usually the first one.
    Always resolve the ticker before calling any other financial data tool.

    Input should be a company name string.
    Examples: "Dangote Cement", "Equity Group Kenya", "Naspers", "MTN"
    """
    try:
        result = await asyncio.to_thread(obb.equity.search, company_name)
        return _to_dict(result)
    except Exception as e:
        return f"Error resolving ticker for '{company_name}': {str(e)}"


# ── Financial Statements ──────────────────────────────────────────────────────
# The following tools use response_format="content_and_artifact": `content`
# is what the LLM sees (identical to what these tools always returned),
# `artifact` is the same raw data object, retrievable directly off the
# ToolMessage during streaming WITHOUT it ever entering the model's
# context a second time. This is what lets the retriever pipeline build
# charts from real tool output rather than re-parsing stringified text.
# On error, content carries the error message (unchanged behavior) and
# artifact is None, signaling "no chart data available for this tool" —
# handled defensively wherever charts are built from these artifacts.

@tool(response_format="content_and_artifact")
async def get_income_statement(symbol: str):
    """
    Use this tool to retrieve a company's annual income statement (profit and loss statement).

    Returns key financial performance metrics including:
    - Revenue and revenue growth trends
    - Cost of goods sold (COGS) and gross profit
    - Gross margin, operating margin, and net profit margin
    - Operating expenses (SG&A, R&D)
    - Earnings Before Interest, Tax, Depreciation and Amortisation (EBITDA)
    - Operating income (EBIT)
    - Interest expense and tax expense
    - Net income and earnings per share (EPS, basic and diluted)
    - Depreciation and amortisation

    Use this when:
    - Analysing a company's profitability and revenue growth over time
    - Calculating profit margins (gross, operating, net)
    - Assessing earnings quality and EPS trends
    - Building or validating a DCF or comparable company valuation model
    - Comparing a company's profitability against its peers

    Returns the last 4 annual periods by default.
    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya),
              "EGH.GH" (Ghana), "AAPL" (US), "COMI.CA" (Egypt)
    """
    try:
        result = await asyncio.to_thread(
            obb.equity.fundamental.income,
            symbol=symbol,
            period="annual",
            limit=4
        )
        data = _to_dict(result)
        return data, data
    except Exception as e:
        error_msg = f"Error retrieving income statement for '{symbol}': {str(e)}"
        return error_msg, None


@tool(response_format="content_and_artifact")
async def get_balance_sheet(symbol: str):
    """
    Use this tool to retrieve a company's annual balance sheet (statement of financial position).

    Returns a snapshot of the company's financial structure including:
    - Total assets, current assets, non-current assets
    - Cash and cash equivalents
    - Accounts receivable and inventory
    - Property, plant and equipment (PP&E)
    - Total liabilities, current liabilities, non-current liabilities
    - Short-term and long-term debt
    - Accounts payable
    - Total shareholders equity and retained earnings
    - Book value per share

    Use this when:
    - Evaluating a company's financial health, solvency and liquidity
    - Calculating debt-to-equity, current ratio, and quick ratio
    - Assessing working capital management
    - Computing price-to-book (P/B) valuation
    - Identifying balance sheet risks such as excessive leverage or low cash reserves
    - Analysing capital structure decisions (debt vs equity financing)

    Particularly important for African companies in high-interest-rate environments
    where debt load and cash position are critical survival indicators.

    Returns the last 4 annual periods by default.
    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = await asyncio.to_thread(
            obb.equity.fundamental.balance,
            symbol=symbol,
            period="annual",
            limit=4
        )
        data = _to_dict(result)
        return data, data
    except Exception as e:
        error_msg = f"Error retrieving balance sheet for '{symbol}': {str(e)}"
        return error_msg, None


@tool(response_format="content_and_artifact")
async def get_cash_flow(symbol: str):
    """
    Use this tool to retrieve a company's annual cash flow statement.

    Returns detailed cash movement data including:
    - Operating cash flow (cash generated from core business operations)
    - Investing cash flow (CapEx, acquisitions, asset sales)
    - Financing cash flow (debt issuance/repayment, dividends, share buybacks)
    - Capital expenditure (CapEx)
    - Free cash flow (operating cash flow minus CapEx)
    - Dividends paid
    - Net change in cash

    Use this when:
    - Assessing whether reported profits are backed by real cash generation
    - Calculating free cash flow for DCF valuation models
    - Identifying signs of earnings manipulation (profit up but cash flow down is a red flag)
    - Evaluating CapEx intensity and reinvestment requirements of the business
    - Understanding how the company funds its operations and growth
    - Checking dividend sustainability (is the dividend covered by free cash flow?)

    Cash flow is often considered more reliable than net income for assessing
    business quality, as it is harder to manipulate through accounting choices.
    This is especially important when researching African companies where
    earnings quality may require additional scrutiny.

    Returns the last 4 annual periods by default.
    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = await asyncio.to_thread(
            obb.equity.fundamental.cash,
            symbol=symbol,
            period="annual",
            limit=4
        )
        data = _to_dict(result)
        return data, data
    except Exception as e:
        error_msg = f"Error retrieving cash flow statement for '{symbol}': {str(e)}"
        return error_msg, None


# ── Company Profile and Overview ──────────────────────────────────────────────
# This tool's own output is rendered as stat tiles/KPI cards, not a chart —
# but chart_data._extract_subject_identity() falls back to it for the subject
# company's symbol + market cap when building the PEER comparison chart. That
# fallback only works if the raw record is captured as an artifact, so this
# tool uses content_and_artifact too. The `content` the model sees is
# unchanged; the artifact is the same dict, captured outside the model's view.

@tool(response_format="content_and_artifact")
async def get_company_overview(symbol: str):
    """
    Use this tool to retrieve a comprehensive overview and profile of a company.

    Returns key identity and descriptive information including:
    - Full company name and stock ticker
    - Stock exchange and trading currency
    - Sector and industry classification
    - Country of incorporation and operations
    - Detailed business description (what the company does)
    - Number of full-time employees
    - Company website
    - Fiscal year end date
    - Market capitalisation
    - 52-week high and low price

    Use this when:
    - Starting research on a company for the first time
    - Writing the company description section of a research report
    - Confirming the correct sector and industry classification
    - Providing context for the AI agent about what the business does
    - Identifying what exchange and currency the stock trades in

    This should typically be one of the first tools called when beginning
    equity research on any company, as it provides essential context
    that informs all subsequent analysis.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya),
              "EGH.GH" (Ghana), "AAPL" (US), "COMI.CA" (Egypt)
    """
    try:
        result = await asyncio.to_thread(obb.equity.profile, symbol=symbol)
        data = _to_dict(result)
        return data, data
    except Exception as e:
        return f"Error retrieving company overview for '{symbol}': {str(e)}", None


@tool(response_format="content_and_artifact")
async def get_key_metrics(symbol: str):
    """
    Use this tool to retrieve pre-calculated valuation ratios and financial metrics for a company.

    Returns a comprehensive set of ready-made ratios including:
    - Price-to-Earnings (P/E) ratio — trailing and forward
    - Price-to-Book (P/B) ratio
    - Price-to-Sales (P/S) ratio
    - Price-to-Free-Cash-Flow (P/FCF)
    - Enterprise Value to EBITDA (EV/EBITDA)
    - Enterprise Value to Revenue (EV/Revenue)
    - Return on Equity (ROE)
    - Return on Assets (ROA)
    - Return on Invested Capital (ROIC)
    - Debt-to-Equity ratio
    - Current ratio and quick ratio
    - Profit margin, operating margin, gross margin
    - Dividend yield and payout ratio
    - Revenue per share, book value per share

    Use this when:
    - Performing comparable company (comps) analysis
    - Quickly assessing whether a stock appears cheap or expensive
    - Comparing valuation multiples across a peer group
    - Writing the valuation section of a research report
    - Screening stocks based on fundamental quality metrics

    These are the core ratios that professional equity analysts use daily.
    Using this tool saves computing them manually from raw financial statements.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = await asyncio.to_thread(
            obb.equity.fundamental.metrics,
            symbol=symbol,
            period="annual",
            limit=4
        )
        data = _to_dict(result)
        return data, data
    except Exception as e:
        error_msg = f"Error retrieving key metrics for '{symbol}': {str(e)}"
        return error_msg, None


# ── Price and Market Data ─────────────────────────────────────────────────────

@tool(response_format="content_and_artifact")
async def get_stock_quote(symbol: str):
    """
    Use this tool to retrieve the current market quote and live price data for a stock.

    Returns real-time (or slightly delayed) market data including:
    - Current stock price
    - Day high and day low
    - 52-week high and 52-week low
    - Market capitalisation
    - Trading volume (today and average)
    - Bid and ask prices
    - Trading currency

    Use this when:
    - Anchoring valuation analysis to the current market price
    - Checking where a stock is trading relative to its 52-week range
    - Verifying the current market cap for enterprise value calculations
    - Getting the most up-to-date price before generating a research report

    Note: For some African exchanges (NGX, GSE, NSE Kenya), Yahoo Finance
    may provide data with a 15-20 minute delay rather than real-time.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya),
              "EGH.GH" (Ghana), "AAPL" (US), "COMI.CA" (Egypt)
    """
    try:
        result = await asyncio.to_thread(obb.equity.price.quote, symbol=symbol)
        data = _to_dict(result)
        return data, data
    except Exception as e:
        error_msg = f"Error retrieving stock quote for '{symbol}': {str(e)}"
        return error_msg, None


# ── Ownership and Capital Structure ───────────────────────────────────────────

@tool(response_format="content_and_artifact")
async def get_share_statistics(symbol: str):
    """
    Use this tool to retrieve shares float and short interest statistics for a company.

    Returns detailed capital structure data including:
    - Total shares outstanding (all issued shares)
    - Float shares (shares freely available for public trading)
    - Short interest (number of shares sold short by bearish traders)
    - Short ratio (days to cover short position at average volume)
    - Short interest as a percentage of float
    - Average 10-day and 3-month trading volume

    Use this when:
    - Computing free float market capitalisation
    - Assessing liquidity risk (small float = price can move on low volume)
    - Identifying high short interest as a potential squeeze risk or bearish signal
    - Understanding the true tradeable share supply for an African company

    Many African companies — especially on smaller exchanges like GSE or BRVM —
    have very small free floats due to government or founding family ownership,
    which explains why prices can be volatile on relatively modest traded volumes.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = await asyncio.to_thread(obb.equity.ownership.share_statistics, symbol=symbol)
        data = _to_dict(result)
        return data, data
    except Exception as e:
        error_msg = f"Error retrieving share statistics for '{symbol}': {str(e)}"
        return error_msg, None


# ── Stock Peers ──────────────────────────────────────────────────────────

import yfinance as yf

@tool(response_format="content_and_artifact")
async def get_stock_peers(symbol: str):
    """
    Retrieve peer companies for competitive analysis.
    Returns peer symbols from yfinance industry data.
    """
    try:
        ticker = yf.Ticker(symbol)
        # ticker.info is a blocking network call under the hood — offload
        # it to a background thread with asyncio.to_thread so it doesn't
        # stall the event loop while it waits on Yahoo Finance.
        info = await asyncio.to_thread(getattr, ticker, "info")
        # yfinance doesn't have a direct peers endpoint
        # but you can fetch industry peers via this approach:
        peers_raw = info.get("recommendedSymbols", [])

        # Fallback: peers agent (already async — awaited directly)
        PEER_MAP = await peers_agent(ticker_symbol=symbol)
        peer_symbols = peers_raw or PEER_MAP.get(symbol.upper(), [])

        async def fetch_peer(s: str) -> dict:
            try:
                p_info = await asyncio.to_thread(lambda: yf.Ticker(s).fast_info)
                return {
                    "symbol":     s,
                    "market_cap": getattr(p_info, "market_cap", None),
                    "last_price": getattr(p_info, "last_price", None),
                }
            except Exception:
                return {"symbol": s}

        # Fetch all peer quotes concurrently instead of one at a time —
        # asyncio.gather runs every fetch_peer() call in parallel, so
        # looking up 8 peers takes roughly as long as looking up 1.
        results = await asyncio.gather(*(fetch_peer(s) for s in peer_symbols[:8]))
        data = list(results)
        return data, data

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        return error_msg, None


@tool
async def tavily(query: str): 
    """
    Search the web for current financial news and market sentiment.

    Search order:
        1. Tavily Search (structured results with source URLs)
        2. DuckDuckGo Search (fallback — plain text, no source URLs)

    IMPORTANT: If the fallback (DuckDuckGo) is used, source URLs will not
    be available for this query. Note this explicitly in your output so
    the References section can reflect it accurately.
    """
    
    response = await tavily_search(query)
    return response
