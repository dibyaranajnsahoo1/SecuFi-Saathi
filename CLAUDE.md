# CLAUDE.md - SecuFi Saathi Round 2 Build Context

## Goal
Turn the Round 1 gap analyzer into a deployable conversational AI agent for Indian households.

The finished repo should let a real user:

1. Describe their family finances in natural conversation.
2. Have the agent decide when to run the gap-analysis tool.
3. Receive a warm, plain-language explanation of gaps.
4. Ask insurance follow-up questions without re-entering all details.
5. Get current-info answers when freshness matters.

This repo is judged more on agent architecture, safety, MCP usage, evaluation quality, and documentation than on fancy UI.

## Product requirements

### R1. LLM integration
- Use native tool or function calling from the model provider.
- Keep the system prompt in a separate file, not inline in application code.
- Preserve multi-turn context so the user can ask follow-ups like "Is Priya covered?" or "What about Priya?".
- Do not use regex parsing of assistant text to trigger tools.

### R2. Gap analyzer tool
- Reuse the Round 1 analyzer as a proper tool.
- The tool input must be defined with a real schema.
- The tool returns structured JSON.
- The model decides when to call the tool.
- The assistant explains the structured result in natural language after the tool call.

### R3. Web search tool
- Provide a web-search path for current questions such as insurer metrics or recent IRDAI rules.
- Use this tool only when freshness matters.
- If the live search fails, say so honestly and fall back to non-current educational guidance.

### R4. Knowledge skill
- The insurance knowledge base must be available on demand.
- Prefer a real retrieval path over stuffing everything into the prompt.
- Keep answers India-specific and educational.
- Do not use the knowledge path when the user is really asking for a household gap calculation.

### R5. MCP integration
- Include at least one MCP server.
- A custom MCP server is preferred.
- Document what it exposes and why.

### R6. Evaluation
- Include at least 5 end-to-end agent eval cases in `evals/evals.py`.
- Check agent behavior, not just analyzer math.
- Cover tool usage, follow-up memory, knowledge retrieval, and safety guardrails.

## Architecture expectations

Keep the code modular:

- `src/agent.py`: orchestration, memory, tool loop
- `src/app.py`: FastAPI transport and chat endpoint
- `src/tools/gap_analyzer.py`: wrapper around Round 1 analysis
- `src/tools/web_search.py`: current-information lookup
- `src/mcp/server.py`: MCP server for knowledge retrieval
- `src/knowledge/indian-insurance.md`: knowledge base
- `src/prompts/system_prompt.md`: persona, tool policy, safety guardrails

Avoid monolithic scripts.

## Conversation behavior

- Start helpfully and invite the user to share family details in any natural format.
- Ask only for missing information needed to do the job.
- When enough household data is available, convert it into the analyzer schema and call the tool.
- Remember the latest report so follow-up questions do not force the user to repeat data.
- If the user updates numbers later, treat that as new context and re-analyze when appropriate.

## Safety guardrails

- Never recommend a specific insurer, product SKU, or guaranteed outcome.
- Never promise claim approval, returns, or exact premiums.
- Never give tax, legal, or claim-dispute advice.
- Do not invent missing values.
- For retired or non-earning parents, explain that life insurance is mainly for income replacement and may not be needed for that purpose.
- If the user asks which insurer to buy from, give evaluation criteria and suggest a licensed adviser for the final decision.

## Writing and UX bar

- Use warm, plain Indian English.
- Prefer `Rs.`, `lakh`, and `crore` wording.
- Explain numbers simply and prioritize the most urgent gap first.
- Be useful to a real Indian family, not just technically correct.

## Implementation notes

- Keep Round 1 analyzer logic deterministic and side-effect free.
- Prefer structured Pydantic models and JSON Schema where possible.
- Make tool failures recoverable with user-friendly fallback messages.
- Keep deployment simple. A minimal browser chat UI is enough.

## Documentation deliverables

- `README.md` must explain setup, run steps, deployment, and requirement mapping.
- `ARCHITECTURE.md` must describe actual decisions and tradeoffs taken in this repo.
- `CLAUDE.md` should reflect the real build instructions for this Round 2 agent, not the old Round 1 analyzer-only assignment.

## What good looks like

When reviewing or extending this repo, optimize for:

- clean separation between prompt, agent loop, tools, MCP, and transport
- reliable tool calling with structured inputs and outputs
- strong follow-up memory
- clear safety behavior
- honest documentation

If forced to choose, prioritize correctness, explainability, and trust over cleverness.
