import asyncio
from datetime import date, datetime
from openbb import obb
from .config import config
from langchain.tools import tool
from .peers_agent import peers_agent
from .tavily_search_tool import tavily_search

# Absolute import — chart_data.py lives at chat/ (this feature's root,
# where chat_agent.py is run directly from), making it a top-level
# importable module on sys.path, not a nested-package sibling of
# chat_tools.py's own tool_set/ package. Same reasoning as the
# response_style import in memory.py/titles.py.
from ..chart_data import (
    shape_income_statement,
    shape_balance_sheet,
    shape_cash_flow,
    shape_key_metrics,
    shape_stock_quote,
    shape_price_history,
    shape_share_statistics,
    shape_stock_peers,
    shape_dividend_history,
)

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
    Converts an OpenBB OBBject result to a plain, JSON-safe dict/list.
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


# ═══════════════════════════════════════════════════════════════════
# PRIVATE FETCH HELPERS
# One per chartable data type. These do the actual I/O and return raw,
# JSON-safe data — and deliberately DO NOT catch exceptions themselves.
# Each public @tool wrapper below catches around its own call to format
# a user-facing error string (matching this project's established
# tool-error behavior); generate_chart (further down) catches around
# its own calls to return a clean chart-generation error instead. This
# split avoids duplicating the actual fetch logic between "the tool the
# LLM calls directly" and "the tool that builds a chart from the same
# underlying data."
# ═══════════════════════════════════════════════════════════════════

async def _fetch_income_statement(symbol: str):
    result = await asyncio.to_thread(
        obb.equity.fundamental.income, symbol=symbol, period="annual", limit=4
    )
    return _to_dict(result)


async def _fetch_balance_sheet(symbol: str):
    result = await asyncio.to_thread(
        obb.equity.fundamental.balance, symbol=symbol, period="annual", limit=4
    )
    return _to_dict(result)


async def _fetch_cash_flow(symbol: str):
    result = await asyncio.to_thread(
        obb.equity.fundamental.cash, symbol=symbol, period="annual", limit=4
    )
    return _to_dict(result)


async def _fetch_key_metrics(symbol: str):
    result = await asyncio.to_thread(
        obb.equity.fundamental.metrics, symbol=symbol, period="annual", limit=4
    )
    return _to_dict(result)


async def _fetch_stock_quote(symbol: str):
    result = await asyncio.to_thread(obb.equity.price.quote, symbol=symbol)
    return _to_dict(result)


async def _fetch_price_history(symbol: str):
    result = await asyncio.to_thread(
        obb.equity.price.historical, symbol=symbol, period="1y"
    )
    return _to_dict(result)


async def _fetch_share_statistics(symbol: str):
    result = await asyncio.to_thread(obb.equity.ownership.share_statistics, symbol=symbol)
    return _to_dict(result)


async def _fetch_dividend_history(symbol: str):
    result = await asyncio.to_thread(obb.equity.fundamental.dividends, symbol=symbol)
    return _to_dict(result)


import yfinance as yf


async def _fetch_stock_peers(symbol: str):
    ticker = yf.Ticker(symbol)
    info = await asyncio.to_thread(getattr, ticker, "info")
    peers_raw = info.get("recommendedSymbols", [])

    peer_map = await peers_agent(ticker_symbol=symbol)
    peer_symbols = peers_raw or peer_map.get(symbol.upper(), [])

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

    results = await asyncio.gather(*(fetch_peer(s) for s in peer_symbols[:8]))
    return list(results)


# ═══════════════════════════════════════════════════════════════════
# PUBLIC TOOLS — unchanged LLM-facing behavior, now delegating to the
# private fetch helpers above instead of duplicating the fetch logic.
# ═══════════════════════════════════════════════════════════════════

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


@tool
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
        return await _fetch_income_statement(symbol)
    except Exception as e:
        return f"Error retrieving income statement for '{symbol}': {str(e)}"


@tool
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
        return await _fetch_balance_sheet(symbol)
    except Exception as e:
        return f"Error retrieving balance sheet for '{symbol}': {str(e)}"


@tool
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
        return await _fetch_cash_flow(symbol)
    except Exception as e:
        return f"Error retrieving cash flow statement for '{symbol}': {str(e)}"


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


@tool
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
        return await _fetch_key_metrics(symbol)
    except Exception as e:
        return f"Error retrieving key metrics for '{symbol}': {str(e)}"


@tool
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
        return await _fetch_stock_quote(symbol)
    except Exception as e:
        return f"Error retrieving stock quote for '{symbol}': {str(e)}"


@tool
async def get_price_history(symbol: str):
    """
    Use this tool to retrieve historical daily price data (OHLCV) for a stock.

    Returns daily Open, High, Low, Close (adjusted), and Volume data
    going back as far as available — often 10 to 20+ years for major companies.

    Use this when:
    - Calculating historical total returns for a stock
    - Measuring price volatility and beta
    - Comparing stock price performance against a benchmark or peers
    - Identifying price trends and chart patterns
    - Computing moving averages or other technical indicators
    - Showing how the stock has performed over 1, 3, and 5-year periods

    For African stocks with low trading liquidity, the volume column is
    especially important — thin volume means prices can be unreliable signals.

    Returns 1 year of daily price history by default.
    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        return await _fetch_price_history(symbol)
    except Exception as e:
        return f"Error retrieving price history for '{symbol}': {str(e)}"


@tool
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
        return await _fetch_share_statistics(symbol)
    except Exception as e:
        return f"Error retrieving share statistics for '{symbol}': {str(e)}"


@tool
async def get_stock_peers(symbol: str):
    """
    Retrieve peer companies for competitive analysis.
    Returns peer symbols from yfinance industry data.
    """
    try:
        return await _fetch_stock_peers(symbol)
    except Exception as e:
        return f"Error: {str(e)}"


@tool
async def get_dividend_history(symbol: str):
    """
    Use this tool to retrieve a company's historical dividend payment record.

    Returns dividend data including:
    - Payment date and ex-dividend date for each historical payment
    - Dividend amount per share, per payment
    - Dividend frequency (annual, semi-annual, quarterly)

    Use this when:
    - Assessing whether a stock is suitable for income/dividend investing
    - Checking dividend growth history (has the company raised its dividend
      consistently, or cut it in the past?)
    - Building a dividend-focused portfolio and comparing yield sustainability
      across candidate companies
    - Cross-checking dividend payout against free cash flow to assess
      whether the dividend is well-covered or at risk

    A consistent, growing dividend history over many years is generally
    viewed as a sign of financial discipline and stability. A history of
    cuts or suspensions is a red flag for income-focused investors.

    Note: many growth-oriented companies (e.g. most tech companies) pay
    no dividend at all — a valid and common result for this tool is an
    empty history, not necessarily an error.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya),
              "EGH.GH" (Ghana), "AAPL" (US), "COMI.CA" (Egypt)
    """
    try:
        return await _fetch_dividend_history(symbol)
    except Exception as e:
        return f"Error retrieving dividend history for '{symbol}': {str(e)}"


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


# ═══════════════════════════════════════════════════════════════════
# CHART TOOL — the only tool in this file using content_and_artifact.
# Unlike Deep Research and Terminal (which batch-build charts from
# whichever data tools happened to run), Chat's chart generation is
# explicitly LLM-driven: the model decides when a chart would help,
# names the company and chart type, and this tool fetches exactly the
# data needed for that one chart. `content` is a short confirmation
# the model sees; `artifact` is the actual chart JSON, captured by
# chat_agent.py's streaming loop the same way Deep Research and
# Terminal capture their own tool artifacts — never re-entering the
# model's context.
# ═══════════════════════════════════════════════════════════════════

CHART_TYPES = (
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "key_metrics",
    "stock_quote",
    "price_history",
    "share_statistics",
    "stock_peers",
    "dividend_history",
)


@tool(response_format="content_and_artifact")
async def generate_chart(symbol: str, chart_type: str):
    """
    Generates chart-ready data for a company to be rendered visually in
    the chat interface. Call this whenever a chart would help illustrate
    your answer — either because the user explicitly asked for one, or
    because you judge a visual would clarify a trend, comparison, or
    composition better than text alone.

    Valid chart_type values:
    - "income_statement" : revenue, profit, and margin trend chart
    - "balance_sheet"    : asset/liability/equity composition and leverage trend
    - "cash_flow"        : operating cash flow, CapEx, and free cash flow trend
    - "key_metrics"      : valuation and quality ratio gauges plus a radar snapshot
    - "stock_quote"      : current price position within its 52-week range
    - "price_history"    : candlestick price chart with volume (x-axis is
      trading-day position, not calendar dates — this data source has no
      reliable per-row date field)
    - "share_statistics" : ownership composition and short interest
    - "stock_peers"      : market cap comparison against direct competitors
    - "dividend_history" : dividend per share paid over time

    Input:
    - symbol: the company's ticker symbol. Resolve it first with
      resolve_ticker_symbol if you were only given a company name.
    - chart_type: one of the exact values listed above.

    This tool prepares a visual only — it does not add to or replace
    your own written analysis. Continue your answer normally; the chart
    renders alongside what you write.
    """
    chart_type_normalized = (chart_type or "").strip().lower()

    if chart_type_normalized not in CHART_TYPES:
        return (
            f"Unknown chart_type '{chart_type}'. Valid options: {', '.join(CHART_TYPES)}",
            None,
        )

    try:
        if chart_type_normalized == "income_statement":
            raw = await _fetch_income_statement(symbol)
            chart = shape_income_statement(raw)

        elif chart_type_normalized == "balance_sheet":
            raw = await _fetch_balance_sheet(symbol)
            chart = shape_balance_sheet(raw)

        elif chart_type_normalized == "cash_flow":
            raw = await _fetch_cash_flow(symbol)
            chart = shape_cash_flow(raw)

        elif chart_type_normalized == "key_metrics":
            raw = await _fetch_key_metrics(symbol)
            chart = shape_key_metrics(raw)

        elif chart_type_normalized == "stock_quote":
            raw = await _fetch_stock_quote(symbol)
            chart = shape_stock_quote(raw)

        elif chart_type_normalized == "price_history":
            raw = await _fetch_price_history(symbol)
            chart = shape_price_history(raw)

        elif chart_type_normalized == "share_statistics":
            raw = await _fetch_share_statistics(symbol)
            chart = shape_share_statistics(raw)

        elif chart_type_normalized == "dividend_history":
            raw = await _fetch_dividend_history(symbol)
            chart = shape_dividend_history(raw)

        elif chart_type_normalized == "stock_peers":
            peers_raw = await _fetch_stock_peers(symbol)
            key_metrics_raw = await _fetch_key_metrics(symbol)
            record = (
                key_metrics_raw[0]
                if isinstance(key_metrics_raw, list) and key_metrics_raw
                else key_metrics_raw
            )
            subject_symbol = symbol.upper()
            subject_market_cap = None
            if isinstance(record, dict):
                subject_symbol = record.get("symbol") or subject_symbol
                subject_market_cap = record.get("market_cap")
            chart = shape_stock_peers(peers_raw, subject_symbol, subject_market_cap)

        else:
            # Unreachable given the membership check above — kept only
            # as a defensive guard so a future CHART_TYPES addition
            # without a matching branch fails loudly instead of silently.
            return f"chart_type '{chart_type_normalized}' has no implementation.", None

        return f"Chart generated for {symbol.upper()} ({chart_type_normalized}).", chart

    except Exception as e:
        return f"Error generating {chart_type_normalized} chart for '{symbol}': {str(e)}", None
