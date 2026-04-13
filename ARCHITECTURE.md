# SecuFi Saathi Architecture

## Why this stack
I reused Python because Round 1 logic and test coverage were already stable in Python. I chose FastAPI because it gives a deployable API and static UI endpoint with minimal boilerplate, which helped keep focus on agent behavior instead of framework setup.  

For LLM provider, I used the OpenAI-compatible SDK path so the same code can run with OpenAI or OpenRouter by switching env vars (`OPENAI_BASE_URL`, `OPENAI_MODEL`). The deciding factors were native tool calling support and low friction for free/low-cost testing.

## Agent architecture
- `src/agent.py`: orchestration loop, session memory, tool execution, final answer generation.
- `src/prompts/system_prompt.md`: persona, safety guardrails, and tool policy.
- `src/tools/gap_analyzer.py`: Round 1 analyzer wrapped as a callable tool.
- `src/tools/web_search.py`: optional freshness tool for current insurer/regulation questions.
- `src/mcp/server.py`: custom MCP server exposing insurance knowledge lookup.

This keeps LLM client, tools, prompt, and app transport modular instead of a monolith.

## Conversation state
In-memory state is keyed by `session_id`:
- complete turn history (`messages`)
- latest gap-analysis report (`last_report`)

This allows follow-ups like "What about Priya?" without re-sharing all household details.  
Tradeoff: in-memory sessions are simple for demo and evals, but data is lost on restart and not shareable across multiple app instances.

## MCP integration
Custom MCP server built with FastMCP and consumed via stdio from the agent.
- Tool exposed: `search_insurance_knowledge(query)`
- Knowledge source: `src/knowledge/indian-insurance.md`
- Transport: subprocess stdio (`python src/mcp/server.py`)

I chose a custom MCP server (instead of prompt stuffing) so protocol integration is explicit and the knowledge layer is reusable independently of this app.

## Tool-calling flow
1. User message enters session.
2. LLM chooses tool(s): `analyze_household`, `search_insurance_knowledge`, `web_search`.
3. Tool returns structured JSON.
4. LLM produces plain-language user response.
5. Agent stores context for future follow-ups.

The agent is not hardcoded with keyword triggers for gap analysis. The model decides tool usage via native function-calling and tool schemas.

## Safety behavior
- System prompt explicitly blocks recommending specific insurers/SKUs.
- Agent responses are constrained to educational guidance and gap explanation.
- Evals verify no insurer recommendation behavior.

## If I had one more week
- Move session memory to Redis for deployment-safe persistence.
- Add retry/fallback model routing for provider errors and rate limits.
- Add structured observability for tool-call frequency, latency, and failure tracing.
- Expand eval harness to assert numerical correctness from normalized extraction rather than keyword matching only.
