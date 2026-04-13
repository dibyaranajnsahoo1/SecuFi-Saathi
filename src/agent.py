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
    from tools.gap_analyzer import get_gap_analyzer_schema, run_gap_analysis
    from tools.web_search import run_web_search
except ImportError:
    from src.tools.gap_analyzer import get_gap_analyzer_schema, run_gap_analysis
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
ANALYZE_HOUSEHOLD_SCHEMA = get_gap_analyzer_schema()


def _format_inr(amount: float) -> str:
    if amount < 0:
        return f"-{_format_inr(-amount)}"
    if amount >= 1_00_00_000:
        return f"Rs. {amount / 1_00_00_000:.2f} crore"
    if amount >= 1_00_000:
        return f"Rs. {amount / 1_00_000:.2f} lakh"
    return f"Rs. {amount:,.0f}"


def _render_gap_report(report: dict[str, Any]) -> str:
    score = report["household_health_score"]
    emergency = report["emergency_fund"]
    life_covers = sorted(
        report["life_cover"],
        key=lambda cover: (cover["existing_cover"] > 0, -cover["gap_amount"]),
    )
    recommendations = report.get("recommendations", [])[:3]
    skipped_members = report.get("skipped_members", [])

    lines = [
        "Overall protection snapshot",
        f"- Health score: {score} / 100",
        "",
        "Emergency fund",
        (
            f"- Available liquid savings: {_format_inr(emergency['total_liquid_savings'])}"
        ),
        (
            f"- Recommended 6-month buffer: {_format_inr(emergency['required_amount'])}"
        ),
        f"- Gap to close: {_format_inr(emergency['gap_amount'])}",
        "",
        "Life cover status",
    ]

    for cover in life_covers:
        name = cover["member_name"]
        if cover["existing_cover"] == 0:
            lines.append(
                f"- {name}: no current life cover. Benchmark need is about "
                f"{_format_inr(cover['required_cover'])}. This is high priority."
            )
        else:
            lines.append(
                f"- {name}: current cover is {_format_inr(cover['existing_cover'])} "
                f"against a benchmark of {_format_inr(cover['required_cover'])}, "
                f"so gap is about {_format_inr(cover['gap_amount'])}."
            )

    if skipped_members:
        lines.append("")
        lines.append("Members not evaluated for life cover")
        for skipped in skipped_members[:2]:
            lines.append(
                f"- {skipped['member_name']}: not included because "
                f"{skipped['reason'].lower()}"
            )

    if recommendations:
        lines.append("")
        lines.append("What to do next")
        for index, recommendation in enumerate(recommendations, start=1):
            lines.append(f"{index}) {recommendation}")

    lines.append("")
    lines.append(
        "If you want, I can break this down member-wise (for example Priya) in the next message."
    )
    return "\n".join(lines)


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
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
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
                    "description": (
                        "Run household emergency fund and life cover gap analysis. "
                        "Use this for a first-pass assessment when you know earning members, "
                        "their annual incomes, total monthly expenses, total liquid savings, "
                        "and current life cover, even if ages or policy details are missing."
                    ),
                    "parameters": ANALYZE_HOUSEHOLD_SCHEMA,
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
            completed_analysis: dict[str, Any] | None = None

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
                    tool_events.append("analyze_household")
                    household_data = args.get("household_data") if "household_data" in args else args
                    if household_data is None:
                        result = {
                            "error": "Missing required household fields for analysis.",
                            "action": (
                                "Ask the user for household member details, income, "
                                "expenses, savings, and existing life cover in conversational form."
                            ),
                        }
                    else:
                        try:
                            result = run_gap_analysis(household_data)
                            state.last_report = result
                            completed_analysis = result
                        except Exception as error:
                            result = {
                                "error": str(error),
                                "action": "Ask the user for any missing or malformed household fields.",
                            }
                elif name == "search_insurance_knowledge":
                    tool_events.append("search_insurance_knowledge")
                    query = args.get("query", "")
                    if not query:
                        result = {
                            "error": "Missing required field: query",
                            "action": "Ask the user what insurance topic they want to understand.",
                        }
                    else:
                        try:
                            result = self.mcp_client.search(query)
                        except Exception as error:
                            result = {
                                "error": str(error),
                                "action": "Answer with general insurance basics and mention that the knowledge tool is unavailable.",
                            }
                elif name == "web_search":
                    tool_events.append("web_search")
                    query = args.get("query", "")
                    if not query:
                        result = {
                            "error": "Missing required field: query",
                            "action": "Ask the user what current topic should be searched.",
                        }
                    else:
                        try:
                            result = run_web_search(query)
                        except Exception as error:
                            result = {
                                "error": str(error),
                                "action": "Tell the user the live web lookup failed and offer a non-current educational answer instead.",
                            }
                else:
                    result = {"error": f"Unknown tool: {name}"}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )
                if name == "analyze_household" and "error" not in result:
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                "You now have a completed household gap-analysis result. "
                                "Explain the result immediately in plain Indian English. "
                                "Do not ask follow-up questions before giving the first-pass analysis. "
                                "If assumptions were used because some optional details were missing, "
                                "mention them briefly after the result."
                            ),
                        }
                    )

            if completed_analysis is not None and len(tool_calls) == 1:
                text = _render_gap_report(completed_analysis)
                state.messages.append({"role": "assistant", "content": text})
                return AgentResponse(session_id=sid, text=text, tool_events=tool_events)


def get_agent() -> SecufiAgent:
    return SecufiAgent()
