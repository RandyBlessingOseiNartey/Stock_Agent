"""
peers_agent.py
--------------
A dedicated sub-agent responsible for discovering stock peer companies
for any given ticker symbol using Tavily search and Pydantic validation.

Output format:
    {"TSLA": ["TM", "GM", "F", "RACE", "RIVN", "NIO", "LI", "STLA"]}

Flow:
    tools.py::get_stock_peers(symbol)
        └── awaits peers_agent(symbol)
                └── agent invokes tavily_search
                        └── raw results parsed + validated by Pydantic
                                └── returns {"TICKER": ["PEER1", "PEER2", ...]}

Note on nested agent visibility: this function creates and runs its own
separate LangGraph agent with its own tool. Because it does not share the
outer retriever agent's callback/streaming context, none of this agent's
internal tool calls will appear in the outer agent's event stream — from
the outside, it looks like a single "get_stock_peers" tool call finished,
exactly as intended.
"""

from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain_tavily import TavilySearch
from pydantic import BaseModel, Field, field_validator, ValidationError
from dotenv import load_dotenv
import json
import re
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from .tavily_search_tool import tavily_search
from langchain.tools import tool

load_dotenv()


# ─────────────────────────────────────────────────────────────────
# SECTION 1 — PYDANTIC MODELS
# Simplified schema — only ticker symbols, no extra fields.
# (unchanged)
# ─────────────────────────────────────────────────────────────────

class PeersResult(BaseModel):
    """
    Validates the agent's output before it is returned.

    source_ticker: the original company being researched (e.g. "TSLA")
    peer_symbols:  list of competitor ticker symbols (e.g. ["GM", "F", "TM"])

    After validation, these are transformed into the final output:
        {"TSLA": ["GM", "F", "TM", ...]}
    """
    source_ticker: str = Field(
        description="The original ticker symbol that was searched e.g. TSLA"
    )
    peer_symbols: list[str] = Field(
        description="List of at least 5 ticker symbols of direct competitor companies",
        min_length=3   # Pydantic rejects fewer than 3 — too sparse to be useful
    )

    @field_validator("source_ticker")
    @classmethod
    def source_must_be_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("peer_symbols")
    @classmethod
    def symbols_must_be_uppercase_and_clean(cls, v: list[str]) -> list[str]:
        """
        Runs on the entire peer_symbols list at once.
        Strips whitespace and uppercases every symbol in the list.
        e.g. ["gm", " F ", "rivn"] → ["GM", "F", "RIVN"]
        Also removes any empty strings that slipped through.
        """
        cleaned = [s.strip().upper() for s in v if isinstance(s, str) and s.strip()]
        return cleaned


# ─────────────────────────────────────────────────────────────────
# SECTION 2 — MODEL INITIALIZATION (unchanged)
# ─────────────────────────────────────────────────────────────────

model = ChatOllama(
        model="gemma4",
        temperature=0,
        base_url="https://ollama.com",
    )


# ─────────────────────────────────────────────────────────────────
# SECTION 3 — TAVILY TOOL (now async)
# ─────────────────────────────────────────────────────────────────
@tool
async def tavily(query: str): 
    """

    Search order:
        1. Tavily Search (structured results with source URLs)
        2. DuckDuckGo Search (fallback — plain text, no source URLs)

    IMPORTANT: If the fallback (DuckDuckGo) is used, source URLs will not
    be available for this query. Note this explicitly in your output so
    the References section can reflect it accurately.
    """
    
    response = await tavily_search(query)
    return response



# ─────────────────────────────────────────────────────────────────
# SECTION 4 — SYSTEM PROMPT (unchanged)
# ─────────────────────────────────────────────────────────────────

PEERS_AGENT_SYSTEM_PROMPT = """
You are a financial data extraction agent. Your ONLY job is to find the 
stock ticker symbols of direct competitor companies for a given ticker symbol.

════════════════════════════════════════
STEP 1 — SEARCH INSTRUCTION
════════════════════════════════════════
You have access to one tool: Tavily Search.

When you receive a ticker symbol, use this EXACT query format:
"[TICKER] direct industry competitors same sector publicly traded ticker symbols [YEAR]"

Example: ticker is TSLA → search: "TSLA direct industry competitors same sector publicly traded ticker symbols 2026"
Example: ticker is AAPL → search: "AAPL direct industry competitors same sector publicly traded ticker symbols 2026"

Use the CURRENT YEAR in the query.
You MUST call the search tool. Do not skip it.

════════════════════════════════════════
STEP 2 — EXTRACTION RULES
════════════════════════════════════════
From the search results, extract at least 5 DIRECT competitor ticker symbols.

CRITICAL RULES — read carefully:
✅ Only include companies that directly compete in the SAME industry and sector
✅ Only include publicly traded companies with a real stock ticker symbol
✅ Extract only the ticker symbol — nothing else (no company names, no exchanges)
❌ Do NOT include the original company itself in the peers list
❌ Do NOT include private companies with no ticker symbol
❌ Do NOT include companies from a different industry or sector
   Example: if searching for TSLA (Auto Manufacturer), do NOT include
   semiconductor companies like NVDA, AMD, TSM, INTC — even if they
   supply chips to Tesla. They are suppliers, not direct competitors.

════════════════════════════════════════
STEP 3 — OUTPUT INSTRUCTION (MANDATORY)
════════════════════════════════════════
After searching, output ONLY a valid JSON object.
No markdown. No explanation. No preamble. No code blocks.
Just the raw JSON starting with { and ending with }.

The JSON must follow this EXACT structure:
{
  "source_ticker": "TSLA",
  "peer_symbols": ["GM", "F", "TM", "RACE", "RIVN", "NIO", "LI", "STLA"]
}

Rules for the output:
- "source_ticker" must be the ticker symbol you were given
- "peer_symbols" must be a JSON array of strings
- Each string must be a ticker symbol only — no company names, no descriptions
- The array must contain at least 5 ticker symbols
- All ticker symbols must be uppercase
"""


# ─────────────────────────────────────────────────────────────────
# SECTION 5 — JSON EXTRACTION HELPER (unchanged — pure string parsing,
# no I/O involved, so nothing here needs to be async)
# ─────────────────────────────────────────────────────────────────

def extract_json_from_text(text: str) -> str:
    """
    Extracts a JSON object from text that may contain markdown
    code fences or surrounding prose.
    """
    # Attempt 1: Strip markdown code fences
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    fence_match   = re.search(fence_pattern, text)
    if fence_match:
        return fence_match.group(1).strip()

    # Attempt 2: Greedy brace extraction
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]

    return text


# ─────────────────────────────────────────────────────────────────
# SECTION 6 — THE PEERS AGENT FUNCTION (now async)
# ─────────────────────────────────────────────────────────────────

async def peers_agent(ticker_symbol: str) -> dict:
    """
    Runs a dedicated LLM agent to discover stock peers for the
    given ticker symbol using Tavily search.

    Args:
        ticker_symbol: A stock ticker e.g. "TSLA", "AAPL"

    Returns:
        A dict in the format: {"TSLA": ["TM", "GM", "F", ...]}
        Returns an empty dict if all retries fail.
    """

    agent = create_agent(
        model=model,
        tools=[tavily],
        system_prompt=PEERS_AGENT_SYSTEM_PROMPT
    )

    agent_input = {
        "messages": [{
            "role": "user",
            "content": f"Find stock peers for ticker symbol: {ticker_symbol.upper()}"
        }]
    }

    max_retries = 4

    for attempt in range(1, max_retries + 1):

        print(f"[peers_agent] Attempt {attempt}/{max_retries} for {ticker_symbol}")

        try:
            # ── Step A: Run the agent ────────────────────────────
            # .ainvoke() instead of .invoke() — this agent is now
            # awaited directly from get_stock_peers (also async),
            # so it no longer blocks the event loop while it thinks
            # and searches.
            response = await agent.ainvoke(agent_input)

            # ── Step B: Extract content ──────────────────────────
            content = response["messages"][-1].content
            if not isinstance(content, str) or not content.strip():
                print(f"[peers_agent] Empty response on attempt {attempt}. Retrying...")
                continue

            # ── Step C: Clean JSON from response ─────────────────
            clean_json = extract_json_from_text(content)

            # ── Step D: Parse JSON ────────────────────────────────
            raw_dict = json.loads(clean_json)

            # ── Step E: Validate with Pydantic ────────────────────
            validated = PeersResult(**raw_dict)

            # ── Step F: Check minimum peer count ─────────────────
            if len(validated.peer_symbols) < 3:
                print(
                    f"[peers_agent] Only {len(validated.peer_symbols)} peers found "
                    f"on attempt {attempt}. Retrying..."
                )
                continue

            # ── Step G: Transform to final output format ──────────
            # Convert from internal Pydantic structure:
            #   PeersResult(source_ticker="TSLA", peer_symbols=["GM", "F", ...])
            # To the exact dict format the pipeline expects:
            #   {"TSLA": ["GM", "F", ...]}
            result = {validated.source_ticker: validated.peer_symbols}

            print(
                f"[peers_agent] Success — {len(validated.peer_symbols)} peers "
                f"found for {ticker_symbol} on attempt {attempt}"
            )
            return result

        except json.JSONDecodeError as e:
            print(f"[peers_agent] JSON parse error on attempt {attempt}: {e}")

        except ValidationError as e:
            print(f"[peers_agent] Pydantic validation error on attempt {attempt}:")
            for error in e.errors():
                print(f"  Field: {error['loc']} | Error: {error['msg']}")

        except Exception as e:
            print(f"[peers_agent] Unexpected error on attempt {attempt}: {e}")

    print(f"[peers_agent] All {max_retries} attempts failed for {ticker_symbol}.")
    return {}