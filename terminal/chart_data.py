"""
chart_data.py
-------------
Reshapes raw tool output (the same dicts get_income_statement,
get_balance_sheet, etc. return) into clean, Plotly.js-ready JSON —
labels, values, and a chart "type" hint — so a future API endpoint can
serve this alongside an agent's report text without the frontend having
to understand OpenBB's raw field names at all.

This module does no LLM calls and no I/O of its own — it's pure data
transformation, run AFTER a tool has already been called (either inside
an agent's tool-calling loop, or separately against cached tool output).
Each function is independent and named after the tool whose output it
expects, so wiring this into a future FastAPI layer is a matter of
calling the right shape_*() function on whichever raw tool result you
already have in hand.

Chart type recommendations (see accompanying explanation delivered
alongside this file):
    get_income_statement   -> grouped bar (revenue/profit lines) + line (margins)
    get_balance_sheet      -> stacked bar (composition) + line (net debt/working capital)
    get_cash_flow          -> combo: OCF/CapEx as bars, FCF as an overlaid line
    get_key_metrics        -> gauge/bullet per ratio + radar for a multi-metric snapshot
    get_stock_peers        -> horizontal bar, ranked by market cap
    get_stock_quote        -> bullet/range chart (52W range with MA50/MA200 markers)
    get_price_history      -> candlestick + volume bars beneath
    get_share_statistics   -> donut (ownership split) + gauge (short % of float)
    get_dividend_history   -> bar chart, dividend per share by period
    get_company_overview   -> not charted — rendered as stat tiles/KPI cards
    tavily                 -> not chartable — unstructured text
"""

def _fmt_period(period_ending) -> str:
    """
    Normalizes a period_ending value to 'YYYY'. period_ending now always
    arrives as an ISO date string (e.g. "2025-12-31"), never a raw
    datetime.date object, since the source tools' _to_dict() applies
    _json_safe() date-conversion before this ever runs — a plain string
    slice is sufficient.
    """
    return str(period_ending)[:4]


# ─────────────────────────────────────────────────────────────────
# INCOME STATEMENT — grouped bar + margin line
# ─────────────────────────────────────────────────────────────────

def shape_income_statement(raw: list[dict]) -> dict:
    """
    Input: get_income_statement's raw list of yearly dicts (most recent first).
    Output: Plotly-ready structure for a grouped bar (revenue/profit tiers)
    and a companion line chart (margin % trends).
    """
    years_desc = raw  # OpenBB returns most-recent-first; reverse for left-to-right charting
    years = [_fmt_period(r["period_ending"]) for r in reversed(years_desc)]

    def _series(key):
        return [round((r.get(key) or 0) / 1e9, 3) for r in reversed(years_desc)]

    revenue = _series("total_revenue")
    gross_profit = _series("gross_profit")
    operating_income = _series("operating_income")
    net_income = _series("net_income")
    ebitda = _series("ebitda")

    margins = {"gross_margin": [], "operating_margin": [], "net_margin": []}
    for r in reversed(years_desc):
        rev = r.get("total_revenue") or 0
        margins["gross_margin"].append(round((r.get("gross_profit") or 0) / rev * 100, 2) if rev else None)
        margins["operating_margin"].append(round((r.get("operating_income") or 0) / rev * 100, 2) if rev else None)
        margins["net_margin"].append(round((r.get("net_income") or 0) / rev * 100, 2) if rev else None)

    return {
        "chart_type": "grouped_bar_plus_line",
        "title": "Revenue, Profit & Margins",
        "x_axis": years,
        "bar_series": {
            "unit": "USD Billions",
            "Revenue": revenue,
            "Gross Profit": gross_profit,
            "Operating Income": operating_income,
            "EBITDA": ebitda,
            "Net Income": net_income,
        },
        "line_series": {
            "unit": "Percent",
            "Gross Margin": margins["gross_margin"],
            "Operating Margin": margins["operating_margin"],
            "Net Margin": margins["net_margin"],
        },
    }


# ─────────────────────────────────────────────────────────────────
# BALANCE SHEET — stacked bar (composition) + line (working capital/net debt)
# ─────────────────────────────────────────────────────────────────

def shape_balance_sheet(raw: list[dict]) -> dict:
    """
    Input: get_balance_sheet's raw list of yearly dicts (most recent first).
    Output: Plotly-ready stacked bar for asset/liability/equity composition,
    plus a line series for Working Capital and Net Debt trend.
    """
    years_desc = raw
    years = [_fmt_period(r["period_ending"]) for r in reversed(years_desc)]

    def _series(key):
        return [round((r.get(key) or 0) / 1e9, 3) for r in reversed(years_desc)]

    return {
        "chart_type": "stacked_bar_plus_line",
        "title": "Balance Sheet Composition & Leverage Trend",
        "x_axis": years,
        "stacked_bar_series": {
            "unit": "USD Billions",
            "Current Assets": _series("total_current_assets"),
            "Non-Current Assets": _series("total_non_current_assets"),
        },
        "stacked_bar_series_liabilities": {
            "unit": "USD Billions",
            "Current Liabilities": _series("current_liabilities"),
            "Non-Current Liabilities": _series("total_non_current_liabilities_net_minority_interest"),
            "Total Equity": _series("total_equity_non_controlling_interests"),
        },
        "line_series": {
            "unit": "USD Billions",
            "Working Capital": _series("working_capital"),
            "Total Debt": _series("total_debt"),
        },
    }


# ─────────────────────────────────────────────────────────────────
# CASH FLOW — combo: OCF/CapEx bars, FCF overlaid line
# ─────────────────────────────────────────────────────────────────

def shape_cash_flow(raw: list[dict]) -> dict:
    """
    Input: get_cash_flow's raw list of yearly dicts (most recent first).
    Output: Plotly-ready combo chart — OCF and CapEx as bars, Free Cash
    Flow as an overlaid line. This is the standard finance-industry FCF
    bridge visualization.
    """
    years_desc = raw
    years = [_fmt_period(r["period_ending"]) for r in reversed(years_desc)]

    ocf = [round((r.get("operating_cash_flow") or 0) / 1e9, 3) for r in reversed(years_desc)]
    capex = [round(abs(r.get("capital_expenditure") or 0) / 1e9, 3) for r in reversed(years_desc)]
    fcf = [round((r.get("free_cash_flow") or 0) / 1e9, 3) for r in reversed(years_desc)]
    sbc = [round((r.get("stock_based_compensation") or 0) / 1e9, 3) for r in reversed(years_desc)]

    return {
        "chart_type": "combo_bar_line",
        "title": "Cash Flow: Operating CF, CapEx & Free Cash Flow",
        "x_axis": years,
        "bar_series": {
            "unit": "USD Billions",
            "Operating Cash Flow": ocf,
            "CapEx": capex,
            "Stock-Based Compensation": sbc,
        },
        "line_series": {
            "unit": "USD Billions",
            "Free Cash Flow": fcf,
        },
    }


# ─────────────────────────────────────────────────────────────────
# KEY METRICS — gauge per ratio + radar snapshot
# ─────────────────────────────────────────────────────────────────

# Benchmark bands mirror the exact thresholds already used in the
# analysis agents' own system prompts (e.g. valuation.txt, solvency.txt),
# so the chart visually agrees with the narrative report instead of
# using a different, uncoordinated scale.
_KEY_METRIC_BENCHMARKS = {
    "pe_ratio":        {"label": "Trailing P/E",  "good_max": 25,  "fair_max": 40},
    "peg_ratio":       {"label": "PEG Ratio",     "good_max": 1.0, "fair_max": 2.0},
    "current_ratio":   {"label": "Current Ratio", "good_max": None, "fair_max": None, "good_min": 2.0, "fair_min": 1.0},
    "quick_ratio":     {"label": "Quick Ratio",   "good_min": 1.0, "fair_min": 0.5},
    "debt_to_equity":  {"label": "Debt/Equity",   "good_max": 1.0, "fair_max": 2.0},
    "return_on_equity":{"label": "ROE",           "good_min": 0.15, "fair_min": 0.10, "is_percent": True},
    "return_on_assets":{"label": "ROA",           "good_min": 0.05, "fair_min": 0.02, "is_percent": True},
}


def shape_key_metrics(raw: dict) -> dict:
    """
    Input: get_key_metrics's raw dict (a single latest snapshot, not a
    time series — most-recent record if the tool call returned a list).
    Output: one gauge spec per benchmarked ratio, plus a radar-chart-
    ready normalized snapshot across a curated set of metrics.
    """
    if isinstance(raw, list) and raw:
        raw = raw[0]  # most recent period

    gauges = []
    for field, bench in _KEY_METRIC_BENCHMARKS.items():
        value = raw.get(field)
        if value is None:
            continue
        # Percent metrics are displayed x100 (0.25 -> 25.0), so their
        # benchmark bands must be scaled the same way — otherwise an ROE of
        # 25% would be plotted against a "good" threshold of 0.15.
        scale = 100 if bench.get("is_percent") else 1
        display_value = round(value * scale, 2) if scale != 1 else round(value, 3)

        def _scaled(key):
            threshold = bench.get(key)
            return None if threshold is None else round(threshold * scale, 4)

        gauges.append({
            "metric": bench["label"],
            "value": display_value,
            "unit": "%" if bench.get("is_percent") else None,
            "good_min": _scaled("good_min"),
            "good_max": _scaled("good_max"),
            "fair_min": _scaled("fair_min"),
            "fair_max": _scaled("fair_max"),
        })

    radar_fields = ["gross_margin", "operating_margin", "profit_margin", "return_on_equity", "return_on_assets"]
    radar = {
        field: round((raw.get(field) or 0) * 100, 2)
        for field in radar_fields
        if raw.get(field) is not None
    }

    return {
        "chart_type": "gauge_set_plus_radar",
        "title": "Key Valuation & Quality Metrics",
        "gauges": gauges,
        "radar": {
            "unit": "Percent",
            "values": radar,
        },
    }


# ─────────────────────────────────────────────────────────────────
# STOCK PEERS — horizontal bar ranked by market cap
# ─────────────────────────────────────────────────────────────────

def shape_stock_peers(raw: list[dict], subject_symbol: str, subject_market_cap: float) -> dict:
    """
    Input: get_stock_peers's raw list [{"symbol":.., "market_cap":.., "last_price":..}, ...],
    plus the subject company's own symbol and market cap (from
    get_company_overview or get_key_metrics) so it can be included in
    the same ranked bar.
    """
    entries = [{"symbol": subject_symbol, "market_cap_b": round((subject_market_cap or 0) / 1e9, 2), "is_subject": True}]
    for peer in raw:
        if not isinstance(peer, dict):
            continue
        entries.append({
            "symbol": peer.get("symbol"),
            "market_cap_b": round((peer.get("market_cap") or 0) / 1e9, 2),
            "is_subject": False,
        })

    entries.sort(key=lambda e: e["market_cap_b"])

    return {
        "chart_type": "horizontal_bar",
        "title": "Peer Market Capitalization Comparison",
        "unit": "USD Billions",
        "entries": entries,
    }


# ─────────────────────────────────────────────────────────────────
# STOCK QUOTE — bullet/range chart (52W range + moving averages)
# ─────────────────────────────────────────────────────────────────

def shape_stock_quote(raw: dict) -> dict:
    """
    Input: get_stock_quote's raw dict (single snapshot, not a time
    series). Output: a bullet/range chart spec — current price
    positioned within the 52-week range, with MA50/MA200 as reference
    markers. A single-point snapshot is better shown as a position-
    within-range chart than a misleading single-bar or line chart.
    """
    if isinstance(raw, list) and raw:
        raw = raw[0]

    return {
        "chart_type": "bullet_range",
        "title": "Price Position — 52-Week Range",
        "unit": raw.get("currency", "USD"),
        "range_low": raw.get("year_low"),
        "range_high": raw.get("year_high"),
        "current_value": raw.get("last_price"),
        "markers": {
            "50-Day MA": raw.get("ma_50d"),
            "200-Day MA": raw.get("ma_200d"),
            "Previous Close": raw.get("prev_close"),
        },
    }


# ─────────────────────────────────────────────────────────────────
# PRICE HISTORY — candlestick + volume bars
# ─────────────────────────────────────────────────────────────────

def shape_price_history(raw: list[dict]) -> dict:
    """
    Input: get_price_history's raw list of daily OHLCV dicts (oldest
    first, as returned by the tool). Output: Plotly-ready candlestick
    data plus a companion volume bar series — the only chart type that
    meaningfully conveys open/high/low/close density; a line chart of
    closes alone would discard most of the information this tool provides.

    x_axis is a 1-indexed positional sequence (1, 2, 3, ...) rather than
    real calendar dates — a deliberate choice, not a workaround: this
    tool's raw output carries no reliable per-row date field, so trading-
    day position is used as the x-axis instead of attempting to infer
    or fabricate dates.
    """
    if not raw or not isinstance(raw, list):
        return {
            "chart_type": "candlestick_plus_volume",
            "title": "Price History (OHLCV)",
            "x_axis": [],
            "candlestick": {"open": [], "high": [], "low": [], "close": []},
            "volume": [],
        }

    return {
        "chart_type": "candlestick_plus_volume",
        "title": "Price History (OHLCV)",
        "x_axis": list(range(1, len(raw) + 1)),
        "x_axis_label": "Trading Day (positional)",
        "candlestick": {
            "open":  [r.get("open") for r in raw],
            "high":  [r.get("high") for r in raw],
            "low":   [r.get("low") for r in raw],
            "close": [r.get("close") for r in raw],
        },
        "volume": [r.get("volume") for r in raw],
    }


# ─────────────────────────────────────────────────────────────────
# SHARE STATISTICS — donut (ownership) + gauge (short % of float)
# ─────────────────────────────────────────────────────────────────

def shape_share_statistics(raw: dict) -> dict:
    """
    Input: get_share_statistics's raw dict. Output: a donut spec for
    ownership composition (insider/institutional/public float) and a
    gauge spec for short interest as % of float, using the same
    benchmark bands defined in sentiment.txt's system prompt.
    """
    if isinstance(raw, list) and raw:
        raw = raw[0]

    insider_pct = round((raw.get("insider_ownership") or 0) * 100, 2)
    institution_pct = round((raw.get("institution_ownership") or 0) * 100, 2)
    public_float_pct = round(max(0.0, 100 - insider_pct - institution_pct), 2)

    short_pct_of_float = round((raw.get("short_percent_of_float") or 0) * 100, 2)

    return {
        "chart_type": "donut_plus_gauge",
        "title": "Ownership Structure & Short Interest",
        "donut": {
            "Insider": insider_pct,
            "Institutional": institution_pct,
            "Public Float": public_float_pct,
        },
        "gauge": {
            "metric": "Short % of Float",
            "value": short_pct_of_float,
            "good_max": 5,     # <5% = low bearish conviction, per sentiment.txt
            "fair_max": 10,    # 5-10% = moderate
            "days_to_cover": raw.get("days_to_cover"),
        },
    }


# ─────────────────────────────────────────────────────────────────
# DIVIDEND HISTORY — bar chart, dividend per share by period
# ─────────────────────────────────────────────────────────────────

def shape_dividend_history(raw: list[dict]) -> dict:
    """
    Input: get_dividend_history's raw list of payment records. Output:
    a simple bar chart of dividend-per-share over time.

    NOTE: this tool is newly added and has not yet been exercised
    against a live call, so the exact field names below (ex_dividend_
    date, amount) are based on OpenBB's documented dividends schema and
    should be verified against real output before wiring this into a
    live chart.
    """
    if not raw or not isinstance(raw, list):
        return {
            "chart_type": "bar",
            "title": "Dividend History",
            "x_axis": [],
            "values": [],
            "note": "No dividend history available — common for growth companies that pay no dividend.",
        }

    dates = [str(r.get("ex_dividend_date") or r.get("date") or "") for r in raw]
    amounts = [r.get("amount") or r.get("dividend") or 0 for r in raw]

    return {
        "chart_type": "bar",
        "title": "Dividend Per Share History",
        "x_axis": dates,
        "values": amounts,
        "field_names_unverified": True,
    }


# ─────────────────────────────────────────────────────────────────
# BATCH CHART BUILDING
# Used by Deep Research and Terminal only — Chat generates charts
# on-demand via its own generate_chart tool instead of batching from
# collected tool artifacts, since Chat's tool usage isn't deterministic.
# ─────────────────────────────────────────────────────────────────

# Maps a tool's name (exactly as it appears in LangChain's on_tool_end
# event) to the shaper function that turns its raw artifact into a
# chart spec. Kept as one comprehensive map shared across every
# feature's copy of this file — a feature that doesn't have a given
# tool (e.g. Deep Research has no get_price_history) simply never has
# that key present in its collected artifacts, so the entry is skipped
# harmlessly rather than needing a separate map per feature.
_SHAPER_MAP = {
    "get_income_statement":  shape_income_statement,
    "get_balance_sheet":     shape_balance_sheet,
    "get_cash_flow":         shape_cash_flow,
    "get_key_metrics":       shape_key_metrics,
    "get_stock_quote":       shape_stock_quote,
    "get_price_history":     shape_price_history,
    "get_share_statistics":  shape_share_statistics,
    "get_dividend_history":  shape_dividend_history,
}


def _extract_subject_identity(artifacts: dict) -> tuple:
    """
    Finds the subject company's own symbol and market cap from whichever
    of get_key_metrics / get_company_overview happened to be called this
    run, so shape_stock_peers() can compare the subject against its
    peers. get_key_metrics is checked first since its market_cap field
    was confirmed present in earlier sample data; get_company_overview
    is the fallback. Returns (None, None) if neither is available or
    usable — callers must handle that gracefully, never assume a result.
    """
    for tool_name in ("get_key_metrics", "get_company_overview"):
        raw = artifacts.get(tool_name)
        if raw is None:
            continue
        record = raw[0] if isinstance(raw, list) and raw else raw
        if not isinstance(record, dict):
            continue
        symbol = record.get("symbol")
        market_cap = record.get("market_cap")
        if symbol and market_cap is not None:
            return symbol, market_cap

    return None, None


def build_chart_batch(artifacts: dict) -> list[dict]:
    """
    Takes the dict of {tool_name: raw_artifact} collected during one
    agent run's tool-calling phase and returns a list of ready-to-emit
    chart events. Every individual chart is wrapped in its own
    try/except — one tool's malformed data or an unexpected shape can
    never take down the rest of the batch, it just gets reported as an
    "error" entry for that one chart instead of raising.

    Args:
        artifacts: {tool_name: raw_data_or_None, ...} — build this by
            capturing each ToolMessage.artifact during on_tool_end
            events in the calling agent's streaming loop.

    Returns:
        A list of dicts, each either:
            {"tool": <name>, "chart": <shaped chart dict>}
        or, if shaping failed for that one tool:
            {"tool": <name>, "error": <human-readable message>}
    """
    charts = []

    for tool_name, shaper in _SHAPER_MAP.items():
        raw = artifacts.get(tool_name)
        if raw is None:
            continue
        try:
            charts.append({"tool": tool_name, "chart": shaper(raw)})
        except Exception as e:
            charts.append({"tool": tool_name, "error": f"Chart generation failed: {e}"})

    peers_raw = artifacts.get("get_stock_peers")
    if peers_raw is not None:
        try:
            subject_symbol, subject_market_cap = _extract_subject_identity(artifacts)
            if subject_symbol is not None:
                charts.append({
                    "tool": "get_stock_peers",
                    "chart": shape_stock_peers(peers_raw, subject_symbol, subject_market_cap),
                })
            else:
                charts.append({
                    "tool": "get_stock_peers",
                    "error": "Could not determine the subject company's market cap for peer comparison.",
                })
        except Exception as e:
            charts.append({"tool": "get_stock_peers", "error": f"Chart generation failed: {e}"})

    return charts
