# SecuFi Saathi Architecture

This document reflects the actual implementation decisions I made for this repo, why I made them, and the tradeoffs I accepted to ship a working Round 2 agent quickly.

## 1) Why this LLM provider choice
I intentionally used the OpenAI-compatible client in `src/agent.py` with configurable environment variables:
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

This gives flexibility to run on either OpenAI directly or an OpenAI-compatible endpoint such as OpenRouter without changing orchestration code.
The practical reasons for this decision:
- **Tool-calling quality:** native function/tool calling is stable and easy to observe.
- **Cost and free-tier flexibility:** model endpoint can be switched for low-cost testing.
- **Deployment simplicity:** one SDK and one message/tool loop across providers.

I selected this approach over provider-specific SDK lock-in because the assignment prioritizes agent behavior and architecture quality, not vendor coupling.

## 2) Why FastAPI/framework approach
I stayed with Python and used FastAPI (`src/app.py`) because Round 1 analyzer logic was already in Python and deterministic.

FastAPI gives:
- a clean REST chat endpoint (`POST /api/chat`)
- an immediate browser entry point (`GET /`)
- straightforward deployment to Render/Vercel

I avoided heavy agent frameworks on purpose to keep tool behavior explicit in code and easier to reason about during eval review and interviews.

## 3) System design and separation of concerns
The code is split by responsibility:
- `src/agent.py`: LLM loop, tool orchestration, session memory
- `src/prompts/system_prompt.md`: persona + safety + tool policy
- `src/tools/gap_analyzer.py`: Round 1 function wrapped with Pydantic schema
- `src/tools/web_search.py`: freshness lookup path
- `src/mcp/server.py`: custom MCP server for insurance knowledge retrieval
- `src/knowledge/indian-insurance.md`: India-specific education content
- `src/app.py`: API transport and minimal UI serving

This prevents a monolithic script and keeps test/eval boundaries clear.

## 4) Conversation state management
Conversation state is maintained in-memory by `session_id`:
- full prior turns (`messages`)
- latest structured analyzer report (`last_report`)

Why this was chosen now:
- fastest way to support multi-turn follow-ups like "What about Priya?"
- enough for eval and demo deployment

Tradeoff:
- state resets on process restart
- not horizontally scalable across multiple app replicas

Interview note: if this moved to production, the first upgrade would be Redis-backed state with TTL and basic conversation metadata for observability.

## 5) Tool-calling implementation details
Tools are registered as native function tools in a single call to `chat.completions.create(..., tools=[...], tool_choice="auto")`.

Important behavior:
- agent does **not** regex-parse assistant text to trigger tools
- model decides whether to call `analyze_household`, `search_insurance_knowledge`, or `web_search`
- gap analyzer returns structured JSON
- assistant converts output to plain Indian English response

For first-pass household assessments, the prompt directs the model to proceed once core fields are available (earners, income, total monthly expenses, liquid savings, existing life cover), instead of blocking on optional details.

I also keep tool wrappers strongly typed with Pydantic schemas so malformed payloads fail early and recover with user-friendly prompts.

## 6) MCP integration details
I implemented a custom MCP server with FastMCP in `src/mcp/server.py`.

### Exposed MCP capability
- `search_insurance_knowledge(query: str) -> dict`
  - loads `src/knowledge/indian-insurance.md`
  - scores text chunks by query-word overlap
  - returns top matching snippets as structured JSON

### Transport and runtime model
- agent starts MCP server over stdio (`python src/mcp/server.py`)
- agent calls MCP tool through `ClientSession`
- results are returned to the same orchestration loop as other tools

Why this approach:
- satisfies explicit MCP requirement with real protocol usage
- keeps insurance education separate from prompt stuffing
- makes knowledge layer reusable and independently extensible

This choice scored better than embedding the full knowledge file inside the system prompt because it preserves prompt budget and keeps retrieval behavior inspectable.

## 7) Safety and policy enforcement
Safety comes from layered controls:
- explicit guardrails in `system_prompt.md`
- retrieval path for educational queries
- eval checks for non-recommendation behavior

Current policy boundaries include:
- no specific insurer or SKU recommendation
- no guarantees about claim approval/returns
- no tax/legal/claim-dispute advice
- clear guidance that life insurance is mainly for income replacement

## 8) Evaluation strategy
`evals/evals.py` executes end-to-end behavior checks against the live agent loop (not just unit math checks):
- tool call behavior for household analysis
- follow-up memory persistence
- safety behavior for retired parent and insurer recommendation questions
- knowledge retrieval behavior
- freshness behavior using web-search tool

Current recorded run: `6/6` pass in `evals/results.md`.

I intentionally test behavior paths (which tool was called, safety boundaries, follow-up memory) because that aligns with the Round 2 scoring rubric better than only validating numeric outputs.

## 9) What I would change with one more week
- move session memory to Redis/Postgres-backed store for production persistence
- add tracing/metrics (tool latency, call counts, failure reasons, token usage)
- add model fallback routing and retries for rate-limit resilience
- harden evals with deterministic mock search fixtures for CI stability
- add multilingual support (Hinglish + major Indian languages) while preserving same guardrails

## 10) Tradeoffs I accepted
- I prioritized deterministic gap-analysis behavior and clear tool boundaries over advanced UI.
- I kept retrieval lightweight (keyword chunk scoring) to stay transparent and easy to debug in an interview setting.
- I chose speed of implementation plus explainability over adding additional infrastructure before it was necessary.

## 11) Interview Q&A shortcuts
- **Why not store everything in the prompt?**  
  I used MCP retrieval so the knowledge layer stays modular, reusable, and auditable.
- **Why no heavy agent framework?**  
  The assignment values explicit tool-use architecture; direct orchestration made behavior easier to verify.
- **What was the highest-risk failure mode?**  
  Losing follow-up context after restart due to in-memory sessions; planned Redis persistence as first production upgrade.
