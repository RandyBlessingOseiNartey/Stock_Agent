
from openbb import obb
from .config import config
from langchain.tools import tool

obb.user.defaults.commands = config["defaults"]["commands"]

def _to_dict(result):
    """
    Converts an OpenBB OBBject result to a plain dict the agent can read.
    Falls back gracefully if conversion fails.
    """
    try:
        df = result.to_dataframe()
        return df.to_dict(orient="records")
    except Exception:
        try:
            return [r.model_dump() for r in result.results]
        except Exception:
            return str(result)



@tool
def get_price_performance(symbol: str):
    """
    Use this tool to retrieve standardised price performance over multiple time horizons.

    Returns percentage price change over standard investment periods:
    - 1 day, 5 days (1 week)
    - 1 month, 3 months, 6 months
    - 1 year, 2 years, 3 years, 5 years

    Use this when:
    - Summarising how a stock has performed over different time horizons
    - Comparing returns across peer companies
    - Writing the price performance section of a research report
    - Identifying whether recent underperformance is short-term or structural
    - Providing a quick return context before deeper fundamental analysis

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = obb.equity.price.performance(symbol=symbol)
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving price performance for '{symbol}': {str(e)}"
    
    
    
    
    
    
@tool
def get_major_holders(symbol: str):
    """
    Use this tool to retrieve the major shareholder ownership breakdown for a company.

    Returns high-level ownership structure including:
    - Percentage of shares held by company insiders (directors, executives)
    - Percentage held by institutional investors (funds, asset managers)
    - Percentage of shares held by the general public (float)
    - Sometimes lists named major shareholders and their stake sizes

    Use this when:
    - Assessing corporate governance quality and ownership concentration
    - Determining whether a company has dominant government, family, or strategic ownership
    - Evaluating alignment of interests between management and shareholders
    - Understanding liquidity risk (high insider/government ownership = small float = volatile price)

    For African companies, high government ownership is common (especially in utilities,
    telecoms, and banking), which can signal regulatory protection but also political risk.
    High founding family ownership is common in Nigerian and Ghanaian consumer companies.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = obb.equity.ownership.major_holders(symbol=symbol)
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving major holders for '{symbol}': {str(e)}"


@tool
def get_institutional_holders(symbol: str):
    """
    Use this tool to retrieve a detailed list of institutional shareholders for a company.

    Returns a table of specific institutional investors including:
    - Institution name (fund manager, asset manager, ETF provider)
    - Number of shares held
    - Percentage of total shares outstanding
    - Date of the most recent filing

    Use this when:
    - Assessing the quality and credibility of the institutional shareholder base
    - Identifying whether major global asset managers (BlackRock, Vanguard, etc.) are invested
    - Understanding the level of foreign institutional interest in an African company
    - Checking for recent increases or decreases in institutional ownership

    The presence of reputable international institutional investors in an African company
    signals a minimum standard of corporate governance, transparency, and investability
    has been met — this is a meaningful quality indicator for African equity research.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = obb.equity.ownership.institutional(symbol=symbol)
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving institutional holders for '{symbol}': {str(e)}"

@tool
def get_earnings_calendar(symbol: str):
    """
    Use this tool to retrieve upcoming and historical earnings announcement dates for a company.

    Returns earnings event data including:
    - Scheduled earnings announcement date
    - Consensus EPS estimate (analyst forecast)
    - Actual EPS reported (for past earnings)
    - Consensus revenue estimate
    - Actual revenue reported (for past earnings)
    - Earnings surprise (actual vs estimate, positive or negative)

    Use this when:
    - Identifying when the next earnings release is (important for report timing)
    - Analysing the company's track record of beating or missing expectations
    - Assessing analyst coverage — thin or absent estimates mean limited coverage
    - Contextualising recent price moves around earnings announcement dates

    Note: For many African companies with limited analyst coverage, consensus
    estimates may be sparse or unavailable. This itself is useful information —
    it signals the company is under-researched, which is often where the
    best investment opportunities exist.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = obb.equity.calendar.earnings(symbol=symbol)
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving earnings calendar for '{symbol}': {str(e)}"


@tool
def get_ipo_calendar(start_date: str, end_date: str):
    """
    Use this tool to retrieve upcoming and recent IPOs (Initial Public Offerings) within a date range.

    Returns IPO event data including:
    - Company name and ticker symbol
    - Stock exchange listing
    - IPO date (or expected date for upcoming IPOs)
    - Offer price or price range
    - Number of shares offered
    - Total offer size (capital raised)
    - Country of the listing company

    Use this when:
    - Tracking new companies entering African stock markets
    - Identifying investment opportunities in newly listed companies
    - Researching the IPO pipeline for a specific exchange or region
    - Providing context on market activity and new listings for a research report

    This is directly sourced from SEC regulatory filings (F-1 and S-1 forms),
    making it authoritative for African companies seeking US listings or ADR programs,
    as well as domestic African exchange listings tracked by Yahoo Finance.

    Input should be date strings in YYYY-MM-DD format.
    Example: start_date="2024-01-01", end_date="2024-12-31"
    """
    try:
        result = obb.equity.calendar.ipo(
            start_date=start_date,
            end_date=end_date
        )
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving IPO calendar for {start_date} to {end_date}: {str(e)}"


@tool
def get_dividend_history(symbol: str):
    """
    Use this tool to retrieve the complete dividend payment history for a company.

    Returns every dividend ever paid including:
    - Ex-dividend date (the cutoff date to qualify for the dividend)
    - Payment date (when the dividend is actually paid)
    - Dividend amount per share
    - Currency of the dividend

    Use this when:
    - Assessing whether a company has a consistent dividend-paying track record
    - Calculating historical dividend yield
    - Checking for dividend cuts or suspensions (major red flags)
    - Computing total shareholder return (price return + dividend return)
    - Evaluating dividend growth rate as a proxy for management confidence

    Many African blue-chip companies — particularly banks (Equity Group, Zenith Bank),
    consumer staples, and telecoms — pay substantial dividends that form a major
    part of their total investment return. Dividend sustainability is a key
    question in African equity research given earnings volatility.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = obb.equity.fundamental.dividends(symbol=symbol)
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving dividend history for '{symbol}': {str(e)}"


# ── News and Sentiment ────────────────────────────────────────────────────────

@tool
def get_company_news(symbol: str):
    """
    Use this tool to retrieve recent news articles specifically about a company.

    Returns recent news items including:
    - Article headline / title
    - Publisher / news source name
    - Full article URL
    - Publication timestamp

    Use this when:
    - Identifying recent events, announcements, or developments affecting a company
    - Finding catalysts that explain recent price movements
    - Gathering information on management commentary, acquisitions, regulatory issues,
      new product launches, or leadership changes not yet reflected in financials
    - Feeding headlines into a sentiment analysis pipeline

    For African companies with limited analyst coverage, news sources are often the
    primary channel through which material information is disclosed. This tool is
    especially important for staying current on company-specific developments
    that would not yet appear in financial statements.

    Input should be a stock ticker symbol including exchange suffix for African stocks.
    Examples: "DANGCEM.LG" (Nigeria), "NPN.JO" (South Africa), "EQTY.NR" (Kenya)
    """
    try:
        result = obb.news.company(symbols=symbol, limit=10)
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving company news for '{symbol}': {str(e)}"


@tool
def get_market_news(limit: int = 10):
    """
    Use this tool to retrieve broad global financial market news not tied to a specific company.

    Returns general market news including:
    - Macroeconomic developments (central bank decisions, inflation data, GDP releases)
    - Commodity price movements (oil, gold, copper — critical for African resource companies)
    - Currency and foreign exchange developments
    - Geopolitical events affecting financial markets
    - Regional African market news where available

    Use this when:
    - Establishing the macroeconomic backdrop for a research report
    - Contextualising a company's recent performance against broader market conditions
    - Identifying sector-wide or market-wide themes affecting African equities
    - Understanding global risk-on/risk-off sentiment that affects emerging markets

    Global macro context is especially important for African equity research — commodity
    prices, USD strength, global interest rates, and risk appetite all have outsized
    effects on African stock markets compared to developed markets.

    Input should be an integer for the number of news articles to return (default is 10).
    """
    try:
        result = obb.news.world(limit=limit)
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving market news: {str(e)}"


# ── Macroeconomic Context ─────────────────────────────────────────────────────

@tool
def get_country_gdp(country: str):
    """
    Use this tool to retrieve GDP data for a specific country.

    Returns GDP levels and growth rates including:
    - Nominal GDP (current prices, in USD)
    - Real GDP growth rate (year-on-year percentage change)
    - GDP per capita
    - Historical GDP series going back decades

    Use this when:
    - Establishing the macroeconomic growth backdrop for a country's equity market
    - Contextualising a company's revenue growth against national GDP growth
    - Assessing whether an economy is expanding or contracting
    - Comparing economic growth rates across African countries

    Sourced from IMF data, which covers all 54 African nations — making this
    the most comprehensive free source for African country GDP data.

    Input should be a country name string.
    Examples: "nigeria", "ghana", "kenya", "south africa", "egypt", "ethiopia"
    """
    try:
        result = obb.economy.gdp(countries=[country])
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving GDP data for '{country}': {str(e)}"


@tool
def get_inflation_data(country: str):
    """
    Use this tool to retrieve Consumer Price Index (CPI) and inflation rate data for a country.

    Returns inflation data including:
    - CPI index level over time
    - Year-on-year inflation rate (percentage change in price level)
    - Historical inflation series

    Use this when:
    - Assessing the inflationary environment a company operates in
    - Determining whether nominal revenue growth represents real growth
    - Understanding the central bank's policy stance (high inflation → high rates)
    - Adjusting financial projections for real vs nominal growth
    - Evaluating currency purchasing power erosion over time

    Inflation is one of the most critical macro variables for African equity research.
    Several African economies have experienced very high or hyperinflationary periods
    (Nigeria, Zimbabwe, Ethiopia, Egypt) that fundamentally affect real investment returns.
    A company with 20% nominal revenue growth in a 30% inflation environment is
    actually shrinking in real terms — this tool provides the context to identify that.

    Input should be a country name string.
    Examples: "nigeria", "ghana", "kenya", "south africa", "egypt"
    """
    try:
        result = obb.economy.cpi(countries=[country])
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving inflation data for '{country}': {str(e)}"


@tool
def get_interest_rates(country: str):
    """
    Use this tool to retrieve central bank interest rate and lending rate data for a country.

    Returns interest rate data including:
    - Central bank policy rate (benchmark rate)
    - Short-term and long-term lending rates
    - Historical rate series

    Use this when:
    - Determining the cost of capital environment for companies in a country
    - Setting the risk-free rate for DCF valuation models
    - Assessing the burden of debt servicing for highly leveraged companies
    - Understanding why equity valuations differ between high-rate and low-rate markets

    Interest rates in Africa range dramatically — from around 4-6% in Morocco
    to over 20% in Nigeria in recent years. This makes the discount rate assumption
    in any valuation model extremely sensitive and country-specific. A Nigerian
    company valued at a 25% discount rate will look very different from a South
    African company valued at a 10% discount rate, even if fundamentals are similar.

    Input should be a country name string.
    Examples: "nigeria", "ghana", "kenya", "south africa", "egypt"
    """
    try:
        result = obb.economy.interest_rates(countries=[country])
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving interest rate data for '{country}': {str(e)}"


@tool
def get_unemployment_data(country: str):
    """
    Use this tool to retrieve unemployment rate data for a specific country.

    Returns unemployment statistics including:
    - Unemployment rate (percentage of labour force without work)
    - Historical unemployment trend

    Use this when:
    - Assessing consumer spending capacity in a market (high unemployment = less spending)
    - Evaluating loan default risk for banking stocks (high unemployment → more bad loans)
    - Understanding labour market tightness for companies with large workforces
    - Contextualising consumer-facing company revenue performance

    Input should be a country name string.
    Examples: "nigeria", "ghana", "kenya", "south africa", "egypt"
    """
    try:
        result = obb.economy.unemployment(countries=[country])
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving unemployment data for '{country}': {str(e)}"


@tool
def get_country_profile(country: str):
    """
    Use this tool to retrieve a comprehensive macroeconomic profile for a country.

    Returns a broad set of structural economic indicators including:
    - Population and demographic data
    - GDP size and per capita income
    - Trade openness (exports + imports as % of GDP)
    - Government fiscal balance (surplus or deficit)
    - Government debt as a percentage of GDP
    - Current account balance
    - Other structural economic indicators

    Use this when:
    - Writing the macroeconomic context section of a country or company research report
    - Comparing the economic fundamentals of different African countries
    - Assessing country risk for foreign investors considering African equities
    - Understanding the structural economic backdrop that shapes a company's operating environment

    Input should be a country ISO 2-letter code string.
    Examples: "NG" (Nigeria), "GH" (Ghana), "KE" (Kenya), "ZA" (South Africa),
              "EG" (Egypt), "ET" (Ethiopia), "TZ" (Tanzania)
    """
    try:
        result = obb.economy.country_profile(country=country)
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving country profile for '{country}': {str(e)}"


@tool
def get_balance_of_payments(country: str):
    """
    Use this tool to retrieve balance of payments data for a country.

    Returns external sector data including:
    - Current account balance (trade in goods, services, income)
    - Trade balance (exports minus imports)
    - Capital account flows
    - Foreign direct investment (FDI) inflows and outflows
    - Foreign exchange reserves

    Use this when:
    - Assessing currency stability risk (chronic current account deficits weaken currency)
    - Evaluating FX risk for companies with USD-denominated debt or import costs
    - Understanding the sustainability of a country's external financing position
    - Contextualising currency depreciation that affects reported earnings

    Particularly important for African companies with significant import dependencies
    (Nigerian manufacturers importing raw materials in USD) or export revenues
    (mining companies earning USD but reporting in local currency).
    A deteriorating balance of payments position foreshadows currency weakness
    that can destroy USD-equivalent investment returns even when local returns are strong.

    Input should be a country name string.
    Examples: "nigeria", "ghana", "kenya", "south africa", "egypt"
    """
    try:
        result = obb.economy.balance_of_payments(country=country)
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving balance of payments for '{country}': {str(e)}"


@tool
def get_economic_indicators(country: str, indicator: str):
    """
    Use this tool to retrieve any specific economic indicator for a country from IMF, FRED, or OECD.

    This is a flexible tool for pulling any economic data series beyond the standard
    GDP, inflation, and interest rate tools. Useful for highly specific research needs.

    Returns a time series for the requested indicator including historical values and dates.

    Common useful indicators for African equity research:
    - "PCPIPCH" — Inflation rate (IMF code)
    - "BCA_NGDPD" — Current account as % of GDP (IMF code)
    - "GGR_NGDP" — Government revenue as % of GDP (IMF)
    - "LP" — Population (IMF code)
    - "GGXCNL_NGDP" — Fiscal balance as % of GDP (IMF code)

    For FRED (US/global benchmarks):
    - "DCOILWTICO" — WTI crude oil price (critical for Nigerian oil companies)
    - "GOLDAMGBD228NLBM" — Gold price (critical for South African mining companies)
    - "DEXUSEU" — USD/EUR exchange rate
    - "FEDFUNDS" — US Federal Funds rate (affects global risk appetite)

    Use this when standard economy tools do not cover the specific indicator needed,
    or when you need commodity price data to contextualise a resource company's performance.

    Input should be a country name string and an indicator code string.
    Example: country="nigeria", indicator="PCPIPCH"
    """
    try:
        result = obb.economy.indicators(
            countries=[country],
            indicators=[indicator]
        )
        return _to_dict(result)
    except Exception as e:
        return f"Error retrieving indicator '{indicator}' for '{country}': {str(e)}"
    
    
    
    
    
    