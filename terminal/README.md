# terminal — twelve single-purpose analysis agents

Each agent answers one question well. The user picks an agent, names a company,
and gets a focused report on that dimension only. **Deterministic per agent:**
each always calls its own fixed toolset.

```
terminal/
├── registry.py          entry point — ANALYSIS_CATALOGUE + run_analysis_stream()
├── agents/
│   ├── shared.py        model factory, prompt loader, streaming/retry engine
│   └── *_agent.py       12 agents, one per analysis type
├── system_prompts/      12 .txt files, one per agent
├── response_style.py
├── chart_data.py
└── tool_set/            11 tools (the 10 from Deep Research + get_price_history)
```

## The catalogue

`registry.py` is the single place that knows every agent — the API builds its
card grid from `ANALYSIS_CATALOGUE`, so adding a 13th agent means one prompt
file, one agent file, and one entry here.

| Key | Focus |
|---|---|
| `income_statement` | Revenue, margins, EPS, earnings quality |
| `balance_sheet` | Asset composition, leverage, working capital |
| `cash_flow` | OCF, FCF, CapEx, SBC, capital allocation |
| `liquidity` | Current/quick/cash ratios, short-term risk |
| `solvency` | Leverage, interest coverage, capital structure |
| `profitability` | ROE, ROA, ROIC, DuPont, margin layers |
| `valuation` | P/E, EV/EBITDA, PEG, P/B, P/S, peer comparison |
| `dcf` | Intrinsic value: WACC, 3 scenarios, terminal value |
| `growth` | Revenue/EPS CAGR, margin trajectory, Rule of 40 |
| `volatility` | Annualized volatility, beta, Sharpe, ATR |
| `sentiment` | Short interest, ownership, news, squeeze risk |
| `competitive_benchmarking` | Peer ranking, relative valuation |

## How one run works

Unlike Deep Research's two stages, an analysis agent **interleaves** tool
calling and report writing in one continuous run. `agents/shared.py` uses that:
pure tool-calling turns produce empty content chunks, so the **first non-empty
chunk** is the reliable signal that tool calling has ended and writing has
begun — exactly the moment the chart batch is emitted.

Order is therefore guaranteed by construction, not by sorting: tool events →
charts → report tokens.

## Run it standalone

```bash
# from the repo root
uv run python -m terminal.registry
```

`run_analysis_stream(analysis_type, company_input, response_style)` returns an
async generator of event dicts (`tool_start`, `tool_end`, `retry`, `chart`,
`token`, `done`, `failed`). An unknown `analysis_type` yields a single `failed`
event — though the API rejects it with a 400 before reaching this point.
`run_analysis()` is a non-streaming convenience wrapper that returns just the
final text.
