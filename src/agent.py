from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

try:
    from tools.gap_analyzer import run_gap_analysis
    from tools.web_search import run_web_search
except ImportError:
    from src.tools.gap_analyzer import run_gap_analysis
    from src.tools.web_search import run_web_search

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except Exception:  # pragma: no cover
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
SYSTEM_PROMPT = (BASE_DIR / "prompts" / "system_prompt.md").read_text(encoding="utf-8")


@dataclass
class SessionState:
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_report: dict[str, Any] | None = None


@dataclass
class AgentResponse:
    session_id: str
    text: str
    tool_events: list[str]


class MCPKnowledgeClient:
    def __init__(self) -> None:
        self.server_script = str(BASE_DIR / "mcp" / "server.py")

    async def _search_async(self, query: str) -> dict[str, Any]:
        if not (ClientSession and StdioServerParameters and stdio_client):
            return {"query": query, "matched_snippets": [], "source": "mcp-not-available"}

        server_params = StdioServerParameters(command="python", args=[self.server_script])

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("search_insurance_knowledge", {"query": query})

        text = ""
        for part in getattr(result, "content", []):
            maybe_text = getattr(part, "text", "")
            if maybe_text:
                text += maybe_text

        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"query": query, "matched_snippets": [text], "source": "mcp-text"}

        return {"query": query, "matched_snippets": [], "source": "mcp-empty"}

    def search(self, query: str) -> dict[str, Any]:
        import asyncio

        return asyncio.run(self._search_async(query))


class SecufiAgent:
    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        base_url = os.getenv("OPENAI_BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", model)
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "1200"))
        self.sessions: dict[str, SessionState] = {}
        self.mcp_client = MCPKnowledgeClient()

    def _get_session(self, session_id: str | None) -> tuple[str, SessionState]:
        sid = session_id or str(uuid.uuid4())
        if sid not in self.sessions:
            self.sessions[sid] = SessionState()
        return sid, self.sessions[sid]

    def chat(self, user_message: str, session_id: str | None = None) -> AgentResponse:
        sid, state = self._get_session(session_id)
        state.messages.append({"role": "user", "content": user_message})
        tool_events: list[str] = []

        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if state.last_report is not None:
            messages.append(
                {
                    "role": "system",
                    "content": "Previous gap report context for follow-ups: " + json.dumps(state.last_report),
                }
            )
        messages.extend(state.messages)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "analyze_household",
                    "description": "Run household emergency fund and life cover gap analysis.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "household_data": {
                                "type": "object",
                                "description": "Household object containing members and financial details.",
                            }
                        },
                        "required": ["household_data"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_insurance_knowledge",
                    "description": "Fetch India-specific insurance education snippets from MCP server.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search web for current insurer or regulation information.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
        ]

        while True:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=self.max_tokens,
            )
            assistant_message = completion.choices[0].message
            messages.append(assistant_message.model_dump())

            tool_calls = assistant_message.tool_calls or []
            if not tool_calls:
                text = assistant_message.content or "I could not generate a reply."
                state.messages.append({"role": "assistant", "content": text})
                return AgentResponse(session_id=sid, text=text, tool_events=tool_events)

            for tool_call in tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                if name == "analyze_household":
                    household_data = args.get("household_data")
                    if household_data is None:
                        result = {
                            "error": "Missing required field: household_data",
                            "action": (
                                "Ask the user for household member details, income, "
                                "expenses, savings, and existing life cover in conversational form."
                            ),
                        }
                    else:
                        try:
                            result = run_gap_analysis(household_data)
                            state.last_report = result
                            tool_events.append("analyze_household")
                        except Exception as error:
                            result = {
                                "error": str(error),
                                "action": "Ask the user for any missing or malformed household fields.",
                            }
                elif name == "search_insurance_knowledge":
                    query = args.get("query", "")
                    if not query:
                        result = {
                            "error": "Missing required field: query",
                            "action": "Ask the user what insurance topic they want to understand.",
                        }
                    else:
                        result = self.mcp_client.search(query)
                        tool_events.append("search_insurance_knowledge")
                elif name == "web_search":
                    query = args.get("query", "")
                    if not query:
                        result = {
                            "error": "Missing required field: query",
                            "action": "Ask the user what current topic should be searched.",
                        }
                    else:
                        result = run_web_search(query)
                        tool_events.append("web_search")
                else:
                    result = {"error": f"Unknown tool: {name}"}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )


def get_agent() -> SecufiAgent:
    return SecufiAgent()
