"""
agent.py
--------
StockAgent Deep Research pipeline.

Two stages:
  1. Retriever Agent      — gathers all financial/market data via tools.
                            Streamed as EVENTS: which tool is being called,
                            when it finishes, and retry attempts if the
                            agent comes back empty. This is the agent's
                            visible "thought process." Chart data is also
                            collected here (via each chartable tool's
                            content_and_artifact return) and emitted as
                            a batch of chart events right after all tool
                            calls finish — before any report-text token
                            streaming begins.
  2. Investment Brief Agent — writes the final report from that data,
                            informed by the user's chosen Risk Appetite.
                            Streamed as TOKENS: the report text appears
                            live, the way a person would watch it being
                            typed.

`run_pipeline_stream()` is the single entry point both a terminal script
and a future FastAPI SSE/WebSocket endpoint can consume: it's an async
generator that yields small, JSON-serializable event dicts as the
pipeline runs. Nothing about its shape assumes a terminal — `main()` at
the bottom is just one example consumer that happens to print to stdout.

Model instantiation: get_model(response_style) is cached via lru_cache
(only 3 possible styles exist), so it's built at most once per process
per style and reused across every request that asks for that style,
rather than rebuilt on every single call.

Charts are NOT sent to either agent's LLM context at any point — they
are pulled directly off each chartable tool's raw artifact (captured
during on_tool_end) and shaped by chart_data.py's pure functions,
entirely outside the model's view.
"""

import asyncio
import os
from functools import lru_cache
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError
from dotenv import load_dotenv

from .response_style import resolve_temperature, RESPONSE_STYLES, DEFAULT_RESPONSE_STYLE
from .risk_appetite import resolve_risk_appetite, RISK_APPETITES, DEFAULT_RISK_APPETITE
from .chart_data import build_chart_batch

from .tool_set.deep_research_agent_tools import (
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    resolve_ticker_symbol,
    get_company_overview,
    get_stock_peers,
    tavily,
    get_key_metrics,
    get_stock_quote,
    get_share_statistics
)

load_dotenv()


@lru_cache(maxsize=3)
def get_model(response_style: str = DEFAULT_RESPONSE_STYLE) -> ChatOllama:
    """
    Builds a ChatOllama instance for the requested Response Style.

    Cached via lru_cache: since there are only 3 possible response_style
    values, this builds each of the 3 instances at most once per process
    and reuses them for every subsequent request that asks for that same
    style — regardless of which user or which stage is asking. This
    avoids repeatedly discarding and rebuilding the underlying HTTP
    client's connection pool on every single call, so concurrent
    requests reuse a warm, already-connected client instead of each
    paying for a fresh connection. Safe for concurrent async use:
    temperature is passed per-call, not mutated on the shared instance,
    so requests at different styles never interfere with each other
    even while sharing cached objects for their own style.
    """
    temperature = resolve_temperature(response_style)
    return ChatOllama(
        model="gemma4",
        temperature=temperature,
        base_url="https://ollama.com",
        num_ctx=32000
    )


# LangGraph counts one "step" per node visit, so a single tool round costs
# two (model → tool). The retriever is required to call all 10 of its tools,
# which alone needs ~21 steps — past LangGraph's default limit of 25 as soon
# as the model re-checks anything. These ceilings are generous on purpose:
# they exist to stop a genuine infinite loop, not to cap normal work.
RETRIEVER_RECURSION_LIMIT = 60
BRIEF_RECURSION_LIMIT = 20  # no tools — one model turn, plus headroom


retriever_agent_toolset = [
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    resolve_ticker_symbol,
    get_company_overview,
    get_stock_peers,
    tavily,
    get_key_metrics,
    get_stock_quote,
    get_share_statistics
]


# THIS IS NECESSARY FOR CROSS PLATFORM INTEGRATION
def load_prompt(file_name: str) -> str:
    base_path = os.path.join(os.path.dirname(__file__), "system_prompts")
    file_path = os.path.join(base_path, file_name)

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


retriever_agent_prompt = load_prompt("retriever_agent.txt")
investment_brief_agent_base_prompt = load_prompt("investment_brief_agent.txt")


def _build_investment_brief_prompt(risk_appetite: str) -> str:
    """
    Appends a directive telling the model exactly which of Section 7's
    three already-defined risk appetite frameworks (Conservative /
    Moderate / Aggressive) to apply for this specific report — the
    frameworks themselves live entirely in investment_brief_agent.txt
    and are not duplicated here.
    """
    resolved = resolve_risk_appetite(risk_appetite)
    directive = (
        f"\n\n"
        f"════════════════════════════════════════\n"
        f"INVESTOR RISK APPETITE FOR THIS REPORT\n"
        f"════════════════════════════════════════\n"
        f"The user has specified: {resolved.upper()}\n"
        f"Apply the {resolved.upper()} framework defined in Section 7 above "
        f"throughout this report, and label it clearly at the top of that section."
    )
    return investment_brief_agent_base_prompt + directive


# ═══════════════════════════════════════════════════════════════════
# STAGE 1 — RETRIEVER AGENT: EVENT / REASONING STREAMING + CHART BATCH
# ═══════════════════════════════════════════════════════════════════

async def retriever_agent_stream(user_message: str, response_style: str = DEFAULT_RESPONSE_STYLE,
                                  max_retries: int = 5):
    """
    Runs the retriever agent and yields its reasoning process live —
    every tool it starts, every tool it finishes — rather than making
    the caller wait silently for the whole thing to complete. Once the
    retriever's own output is ready (all tool calls done, JSON built),
    emits a batch of chart events built from whatever chartable tools
    were actually called this run — always before Stage 2 begins.

    If get_stock_peers internally runs its own nested peers_agent, that
    nested agent's own tool calls do NOT appear here. It is a fully
    separate agent instantiated inside the tool's implementation with
    no shared callback context, so from here it looks like exactly one
    tool ("get_stock_peers") started and finished — nothing more.

    Args:
        response_style: "precise" | "balanced" | "exploratory" — resolved
            to a temperature via response_style.py. Defaults to "balanced".

    Yields:
        {"type": "tool_start", "tool": <name>}
        {"type": "tool_end",   "tool": <name>}
        {"type": "retry", "attempt": n, "max_retries": max_retries}
        {"type": "chart", "tool": <name>, "chart": <dict>}          (success)
        {"type": "chart", "tool": <name>, "error": <str>}           (per-chart failure)
        {"type": "retriever_done",   "content": <json string>}
        {"type": "retriever_failed", "content": <error message>}
    """
    model = get_model(response_style)
    agent = create_agent(
        model=model,
        tools=retriever_agent_toolset,
        system_prompt=retriever_agent_prompt
    )
    agent_input = {"messages": [{"role": "user", "content": user_message}]}

    for attempt in range(1, max_retries + 1):

        if attempt > 1:
            print(f"[retriever_agent]: Empty content, retrying... (attempt: {attempt}/{max_retries})")
            yield {"type": "retry", "attempt": attempt, "max_retries": max_retries}

        final_content = ""
        collected_artifacts = {}
        hit_step_limit = False

        # astream_events is what makes the tool-calling trace visible.
        # Every step the underlying LangGraph agent takes — starting a
        # tool, finishing a tool, streaming a token from the model — is
        # emitted as its own event here, in real time, instead of only
        # being available after the whole run finishes.
        try:
            async for event in agent.astream_events(
                agent_input,
                version="v2",
                config={"recursion_limit": RETRIEVER_RECURSION_LIMIT},
            ):
                kind = event["event"]

                if kind == "on_tool_start":
                    yield {"type": "tool_start", "tool": event["name"]}

                elif kind == "on_tool_end":
                    yield {"type": "tool_end", "tool": event["name"]}

                    # Capture the raw artifact (if this tool used
                    # response_format="content_and_artifact") without ever
                    # exposing it to the model. Wrapped defensively — an
                    # unexpected event shape here must never break the
                    # stream, it should just mean no chart data for that tool.
                    try:
                        output = event["data"].get("output")
                        artifact = getattr(output, "artifact", None)
                        if artifact is not None:
                            collected_artifacts[event["name"]] = artifact
                    except Exception as e:
                        print(f"[retriever_agent] Could not capture artifact for {event['name']}: {e}")

                elif kind == "on_chat_model_stream":
                    # Not surfaced to the user during this stage — the
                    # retriever's job is to gather JSON data, not narrate
                    # prose, so only its tool-calling activity is streamed.
                    # Tool-call-only messages produce empty content chunks,
                    # so simply accumulating every chunk here isolates the
                    # model's final JSON answer once tool-calling is done.
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        final_content += chunk.content

        except GraphRecursionError:
            # The agent kept taking steps without settling on an answer —
            # a stuck tool-calling loop, not a transient empty response, so
            # retrying the identical input would almost certainly stick the
            # same way. Report it in plain language and stop.
            print(f"[retriever_agent] Hit the {RETRIEVER_RECURSION_LIMIT}-step limit.")
            hit_step_limit = True

        if hit_step_limit:
            yield {
                "type": "retriever_failed",
                "content": (
                    "The research agent kept calling tools without reaching a conclusion "
                    f"and was stopped after {RETRIEVER_RECURSION_LIMIT} steps. "
                    "This usually means a data source kept returning unusable results. "
                    "Try again, or narrow the query to a single company or ticker."
                ),
            }
            return

        if isinstance(final_content, str) and final_content.strip():
            # Charts are built once, in a batch, right here — after
            # every tool call for this run has finished, and strictly
            # before Stage 2's token streaming begins. Wrapped so that
            # a failure in chart building can never take down an
            # otherwise-successful retriever run.
            try:
                for chart_event in build_chart_batch(collected_artifacts):
                    yield {"type": "chart", **chart_event}
            except Exception as e:
                print(f"[retriever_agent] Chart batch generation failed: {e}")

            yield {"type": "retriever_done", "content": final_content}
            return

    error_message = "Error: retriever_agent failed to produce a response after multiple attempts."
    yield {"type": "retriever_failed", "content": error_message}


# ═══════════════════════════════════════════════════════════════════
# STAGE 2 — INVESTMENT BRIEF AGENT: LLM TOKEN STREAMING
# ═══════════════════════════════════════════════════════════════════

async def investment_brief_agent_stream(retriever_output: str, response_style: str = DEFAULT_RESPONSE_STYLE,
                                          risk_appetite: str = DEFAULT_RISK_APPETITE):
    """
    Runs the investment brief agent (no tools — pure reasoning and
    writing) and yields each token of the final report as it is
    generated, so the report appears to the user the way it's actually
    being written rather than arriving all at once after a long wait.

    Args:
        response_style: "precise" | "balanced" | "exploratory".
        risk_appetite: "conservative" | "moderate" | "aggressive" —
            determines which of Section 7's three frameworks the report
            applies. Defaults to "moderate".

    Yields:
        {"type": "token", "content": <chunk of text>}
        {"type": "brief_done", "content": <full report text>}
    """
    model = get_model(response_style)
    system_prompt = _build_investment_brief_prompt(risk_appetite)
    agent = create_agent(model=model, system_prompt=system_prompt)
    agent_input = {"messages": [{"role": "user", "content": retriever_output}]}

    full_text = ""
    async for event in agent.astream_events(
        agent_input,
        version="v2",
        config={"recursion_limit": BRIEF_RECURSION_LIMIT},
    ):
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                full_text += chunk.content
                yield {"type": "token", "content": chunk.content}

    yield {"type": "brief_done", "content": full_text}


# ═══════════════════════════════════════════════════════════════════
# FULL PIPELINE — single async generator, ready for a FastAPI
# SSE/WebSocket layer to consume directly
# ═══════════════════════════════════════════════════════════════════

async def run_pipeline_stream(user_message: str, response_style: str = DEFAULT_RESPONSE_STYLE,
                               risk_appetite: str = DEFAULT_RISK_APPETITE):
    """
    Orchestrates both stages and yields every event from both, each
    tagged with its stage, so any consumer (terminal, SSE, WebSocket)
    can tell which part of the pipeline produced it.

    response_style applies to both stages (one style per research run,
    not one per stage). risk_appetite only affects Stage 2, since the
    retriever's job is pure data gathering and has no notion of
    investor risk tolerance.
    """
    yield {"type": "stage", "stage": "retriever", "status": "start"}

    retriever_content = None
    retriever_failed = False
    async for event in retriever_agent_stream(user_message, response_style):
        event["stage"] = "retriever"
        yield event
        if event["type"] == "retriever_done":
            retriever_content = event["content"]
        elif event["type"] == "retriever_failed":
            retriever_failed = True

    yield {"type": "stage", "stage": "retriever", "status": "end"}

    # With no retrieved data, Stage 2 would be writing a report from an
    # error string — exactly the "figures it never fetched" failure this
    # product exists to prevent. Stop here; retriever_failed is terminal.
    if retriever_failed:
        return

    yield {"type": "stage", "stage": "investment_brief", "status": "start"}

    async for event in investment_brief_agent_stream(retriever_content, response_style, risk_appetite):
        event["stage"] = "investment_brief"
        yield event

    yield {"type": "stage", "stage": "investment_brief", "status": "end"}


# ═══════════════════════════════════════════════════════════════════
# TERMINAL CONSUMER
# One example of consuming run_pipeline_stream(). A FastAPI endpoint
# would instead forward each `event` dict to the browser (e.g. as an
# SSE `data: {json.dumps(event)}\n\n` line) instead of printing it.
# ═══════════════════════════════════════════════════════════════════

async def main():
    inputs = input("Hi, I'm StockAgent, How may I help you today: ")
    response_style = input(
        f"Response style [{'/'.join(RESPONSE_STYLES.keys())}] "
        f"(Enter for {DEFAULT_RESPONSE_STYLE}): "
    ).strip().lower() or DEFAULT_RESPONSE_STYLE
    risk_appetite = input(
        f"Risk appetite [{'/'.join(RISK_APPETITES)}] "
        f"(Enter for {DEFAULT_RISK_APPETITE}): "
    ).strip().lower() or DEFAULT_RISK_APPETITE

    async for event in run_pipeline_stream(inputs, response_style, risk_appetite):
        etype = event["type"]

        if etype == "stage":
            label = "Retrieving Data" if event["stage"] == "retriever" else "Writing Investment Brief"
            if event["status"] == "start":
                print(f"\n▶ {label}...\n")
            else:
                print(f"\n■ {label} finished.\n")

        elif etype == "tool_start":
            print(f"🔧 Calling {event['tool']}...")

        elif etype == "tool_end":
            print(f"✓ {event['tool']} completed.")

        elif etype == "retry":
            print(f"🔁 Retrying... (attempt {event['attempt']}/{event['max_retries']})")

        elif etype == "chart":
            if "chart" in event:
                print(f"📊 Chart ready: {event['tool']} ({event['chart'].get('chart_type', 'unknown')})")
            else:
                print(f"⚠ Chart skipped for {event['tool']}: {event.get('error')}")

        elif etype == "retriever_failed":
            print(f"⚠ {event['content']}")

        elif etype == "token":
            print(event["content"], end="", flush=True)

        elif etype == "brief_done":
            print()  # final newline once the streamed report finishes


if __name__ == "__main__":
    asyncio.run(main())
