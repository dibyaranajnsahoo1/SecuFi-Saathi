from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

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
SYSTEM_PROMPT = (BASE_DIR / "prompts" /
                 "system_prompt.md").read_text(encoding="utf-8")
ANALYZE_HOUSEHOLD_SCHEMA = get_gap_analyzer_schema()


def _looks_like_internal_reasoning(text: str) -> bool:
    lowered = (text or "").strip().lower()
    reasoning_markers = [
        "i need to parse",
        "let's extract",
        "now we need to",
        "i should call",
        "we need to call",
        "members:",
        "household:",
        "annual income",
        "existing cover",
    ]
    return any(marker in lowered for marker in reasoning_markers)


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
    
    # Try to find a dependent's name, or just use the first member's name as an example
    example_name = "Priya"
    if life_covers:
        if len(life_covers) > 1:
            example_name = life_covers[1]["member_name"]
        else:
            example_name = life_covers[0]["member_name"]
            
    lines.append(
        f"If you want, I can break this down member-wise (for example {example_name}) in the next message."
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

        server_params = StdioServerParameters(
            command="python", args=[self.server_script])

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
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "1000"))
        self.sessions: dict[str, SessionState] = {}
        self.mcp_client = MCPKnowledgeClient()

    @staticmethod
    def _extract_affordable_max_tokens(error: Exception) -> int | None:
        message = str(error)
        match = re.search(r"can only afford (\d+)", message)
        if not match:
            return None
        return max(64, int(match.group(1)) - 32)

    def _create_completion_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        attempts = [self.max_tokens, min(self.max_tokens, 700), 500, 300, 200]
        seen: set[int] = set()
        for token_limit in attempts:
            if token_limit in seen:
                continue
            seen.add(token_limit)
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.0,
                    seed=42,
                    max_tokens=token_limit,
                )
            except APIStatusError as error:
                if error.status_code != 402:
                    raise
                affordable_limit = self._extract_affordable_max_tokens(error)
                if affordable_limit and affordable_limit not in seen:
                    try:
                        return self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            tools=tools,
                            tool_choice="auto",
                            temperature=0.0,
                            seed=42,
                            max_tokens=affordable_limit,
                        )
                    except APIStatusError:
                        pass
                continue

        raise RuntimeError(
            "I could not complete the response because your model credits are too low for the current token limit. "
            "Please reduce OPENAI_MAX_TOKENS (for example 300-600) or add credits in your model provider account."
        )

    def _get_session(self, session_id: str | None) -> tuple[str, SessionState]:
        sid = session_id or str(uuid.uuid4())
        if sid not in self.sessions:
            self.sessions[sid] = SessionState()
        return sid, self.sessions[sid]

    def chat(self, user_message: str, session_id: str | None = None) -> AgentResponse:
        sid, state = self._get_session(session_id)
        state.messages.append({"role": "user", "content": user_message})
        tool_events: list[str] = []

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}]
        if state.last_report is not None:
            # Format the cached report to make member names and coverage info explicit
            report_summary = "Previous gap analysis is cached. Use this for follow-ups (do NOT re-analyze):\n"
            life_covers = state.last_report.get("life_cover", [])
            for cover in life_covers:
                member = cover.get("member_name", "Unknown")
                existing = cover.get("existing_cover", 0)
                gap = cover.get("gap_amount", 0)
                report_summary += f"- {member}: existing cover ₹{existing:,.0f}, gap ₹{gap:,.0f}\n"

            emergency = state.last_report.get("emergency_fund", {})
            total_savings = emergency.get("total_liquid_savings", 0)
            recommended = emergency.get("recommended_liquid_savings", 0)
            report_summary += f"- Emergency fund: ₹{total_savings:,.0f} available, ₹{recommended:,.0f} recommended\n"

            report_summary += f"- Overall health score: {state.last_report.get('household_health_score', 'N/A')} / 100\n"
            report_summary += "For follow-up questions about specific members or gaps, use this cached data instead of re-analyzing."

            messages.append(
                {
                    "role": "system",
                    "content": report_summary,
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

        rewrite_attempts = 0
        while True:
            completion = self._create_completion_with_retry(messages, tools)
            assistant_message = completion.choices[0].message
            messages.append(assistant_message.model_dump())
            completed_analysis: dict[str, Any] | None = None

            tool_calls = assistant_message.tool_calls or []
            if not tool_calls:
                text = assistant_message.content or "I could not generate a reply."
                if _looks_like_internal_reasoning(text) and rewrite_attempts < 2:
                    rewrite_attempts += 1
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Do not reveal your internal analysis or planning steps. "
                                "Give only the final user-facing answer. "
                                "If the user gave enough household details, call analyze_household first."
                            ),
                        }
                    )
                    continue
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
                    household_data = args.get(
                        "household_data") if "household_data" in args else args
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