"""
_shared.py
----------
Everything the 12 analysis agents have in common: the model factory, the
prompt loader, and the streaming/retry engine. Each individual agent file
(e.g. income_statement_agent.py) imports from here instead of duplicating
this logic 12 times.

Streaming order is guaranteed by construction, not by any extra sorting
logic: astream_events() naturally emits a tool's on_tool_start/on_tool_end
events during the rounds where the model is calling tools, and only
starts emitting on_chat_model_stream chunks with real text once the model
has the tool results back and begins writing its actual report. So the
event trace always finishes before the first token appears — exactly the
behavior requested.

Model instantiation: the model is now built PER REQUEST via get_model(),
not once at module import time. This is what allows each user to choose
their own Response Style (Precise / Balanced / Exploratory) — a cheap,
in-memory ChatOllama object is cached per Response Style (see lru_cache
on get_model below) rather than one shared instance with a fixed
temperature, or a brand new instance rebuilt on every single call.
"""

import os
from functools import lru_cache
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError
from dotenv import load_dotenv

from ..response_style import resolve_temperature, DEFAULT_RESPONSE_STYLE
from ..chart_data import build_chart_batch

load_dotenv()

# LangGraph counts one "step" per node visit, so a tool round costs two
# (model → tool). The busiest analysis agents use 5 tools, and the default
# limit of 25 leaves little room once the model re-checks anything. High
# enough to never interrupt normal work; low enough to stop a real loop.
RECURSION_LIMIT = 40


@lru_cache(maxsize=3)
def get_model(response_style: str = DEFAULT_RESPONSE_STYLE) -> ChatOllama:
    """
    Builds a ChatOllama instance for the requested Response Style.

    Cached via lru_cache: only 3 possible response_style values exist,
    so each of the 3 instances is built at most once per process and
    reused by every subsequent call asking for that same style —
    across all 12 analysis agents and all users. Avoids rebuilding the
    underlying HTTP client's connection pool on every single agent run,
    so concurrent requests reuse a warm, already-connected client.
    Temperature is passed per-call, not mutated on the shared instance,
    so this is safe under concurrent async use.
    """
    temperature = resolve_temperature(response_style)
    return ChatOllama(
        model="gemma4",
        temperature=temperature,
        base_url="https://ollama.com",
        num_ctx=32000,
    )


def load_prompt(file_name: str) -> str:
    """
    Loads a system prompt .txt file from the system_prompts/ folder that
    sits alongside the agents/ folder (i.e. one level up from this file).
    """
    base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "system_prompts")
    file_path = os.path.join(base_path, file_name)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


async def run_agent_stream(agent_name: str, tools: list, system_prompt: str,
                            company_input: str, response_style: str = DEFAULT_RESPONSE_STYLE,
                            max_retries: int = 4):
    """
    Shared async generator used by every analysis agent. Streams:
        1. Tool-call events first  ("🔧 Calling get_income_statement...")
        2. Final report tokens second (the model's actual prose)
    with full retry-and-restream behavior if the model returns empty
    content — identical pattern to the deep research pipeline, just
    applied to a single tool-using agent instead of a two-agent pipeline
    (each analysis agent both gathers its own data and writes its own
    report in one continuous run).

    Args:
        response_style: "precise" | "balanced" | "exploratory" — resolved
            to a temperature via response_style.py. Defaults to "balanced"
            if not provided or unrecognized.

    Yields:
        {"type": "tool_start", "tool": <name>}
        {"type": "tool_end",   "tool": <name>}
        {"type": "retry", "attempt": n, "max_retries": max_retries}
        {"type": "chart", "tool": <name>, "chart": <dict>}          (success)
        {"type": "chart", "tool": <name>, "error": <str>}           (per-chart failure)
        {"type": "token", "content": <chunk of text>}
        {"type": "done",   "content": <full report text>}
        {"type": "failed", "content": <error message>}
    """
    model = get_model(response_style)
    agent = create_agent(model=model, tools=tools, system_prompt=system_prompt)
    agent_input = {"messages": [{"role": "user", "content": company_input}]}

    for attempt in range(1, max_retries + 1):

        if attempt > 1:
            print(f"[{agent_name}] Empty content, retrying... (attempt: {attempt}/{max_retries})")
            yield {"type": "retry", "attempt": attempt, "max_retries": max_retries}

        final_content = ""
        collected_artifacts = {}
        charts_emitted = False
        hit_step_limit = False

        try:
            async for event in agent.astream_events(
                agent_input,
                version="v2",
                config={"recursion_limit": RECURSION_LIMIT},
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
                        print(f"[{agent_name}] Could not capture artifact for {event['name']}: {e}")

                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        # Unlike Deep Research's 2-stage pipeline, a single
                        # analysis agent interleaves tool-calling and report-
                        # writing in one continuous run. Pure tool-call turns
                        # produce empty content chunks; the FIRST non-empty
                        # chunk is therefore the reliable signal that the
                        # model has stopped calling tools and started writing
                        # its actual answer — exactly the boundary charts
                        # need to be emitted before, per the "batch after
                        # tool calls, before token streaming" design.
                        if not charts_emitted:
                            try:
                                for chart_event in build_chart_batch(collected_artifacts):
                                    yield {"type": "chart", **chart_event}
                            except Exception as e:
                                print(f"[{agent_name}] Chart batch generation failed: {e}")
                            charts_emitted = True

                        final_content += chunk.content
                        # Unlike the deep research retriever stage, this
                        # agent's chat output IS the user-facing report, so
                        # every token is streamed live as it's produced.
                        yield {"type": "token", "content": chunk.content}

        except GraphRecursionError:
            # A stuck tool-calling loop, not a transient empty response —
            # retrying the identical input would stick the same way.
            print(f"[{agent_name}] Hit the {RECURSION_LIMIT}-step limit.")
            hit_step_limit = True

        if hit_step_limit:
            yield {
                "type": "failed",
                "content": (
                    f"The {agent_name} agent kept calling tools without reaching a conclusion "
                    f"and was stopped after {RECURSION_LIMIT} steps. This usually means a data "
                    "source kept returning unusable results. Try again, or use the company's "
                    "ticker symbol directly."
                ),
            }
            return

        if final_content.strip():
            yield {"type": "done", "content": final_content}
            return

    error_message = f"Error: {agent_name} failed to produce a response after {max_retries} attempts."
    print(f"[{agent_name}] All {max_retries} attempts failed.")
    yield {"type": "failed", "content": error_message}


async def run_agent(agent_name: str, tools: list, system_prompt: str,
                     company_input: str, response_style: str = DEFAULT_RESPONSE_STYLE,
                     max_retries: int = 4) -> str:
    """
    Convenience non-streaming wrapper. Consumes run_agent_stream() fully
    and returns just the final report text — for callers (tests, batch
    jobs, non-streaming API routes) that don't need the live event feed.
    """
    final_text = ""
    async for event in run_agent_stream(agent_name, tools, system_prompt, company_input,
                                          response_style, max_retries):
        if event["type"] in ("done", "failed"):
            final_text = event["content"]
    return final_text
