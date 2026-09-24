from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langchain_community.tools import DuckDuckGoSearchRun
import json


#ACTUALLY THIS TOOL IS A COMBINATION OF TAVILY AND DUCKDUCKGO AS WEB SEARCH TOOL



load_dotenv()


# Instantiate once at module load — not on every call
_tavily_client = TavilySearch(
    max_results=5,
    topic="finance",
    include_answer=True,
    search_depth="basic",
    time_range="month",
)

_duckduckgo_client = DuckDuckGoSearchRun()


async def tavily_search(query: str) -> str:

    try:
        # .ainvoke() is used instead of .invoke(). TavilySearch and
        # DuckDuckGoSearchRun are both LangChain BaseTool instances, and
        # every BaseTool exposes .ainvoke() automatically — if the tool
        # has no native async implementation, LangChain runs it in a
        # background thread for you. This means the search no longer
        # blocks the event loop, so many concurrent users can each have
        # a web search in flight at the same time without one request
        # stalling every other request on the server.
        result = await _tavily_client.ainvoke(query)
        return json.dumps({
            "provider": "tavily",
            "has_source_urls": True,
            "result": result,
        })

    except Exception as tavily_error:
        try:
            result = await _duckduckgo_client.ainvoke(query)
            return json.dumps({
                "provider": "duckduckgo",
                "has_source_urls": False,
                "result": result,
                "note": "Fallback provider used — no source URLs available for this search."
            })

        except Exception as duck_error:
            return json.dumps({
                "provider": "none",
                "error": True,
                "tavily_error": f"{type(tavily_error).__name__}: {tavily_error}",
                "duckduckgo_error": f"{type(duck_error).__name__}: {duck_error}",
            })