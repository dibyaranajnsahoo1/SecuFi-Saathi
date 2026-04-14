# SecuFi Saathi – Implementation

I built this AI assistant using Cursor as my main development tool. I already had my Round 1 Gap Analyzer code, so I used Cursor to extend that into a full assistant by giving it the new requirements.

Instead of writing everything from scratch, I guided Cursor step by step:
- I explained that I already have a working analyzer
- Then I asked it to build the surrounding structure like mention in problem description.
- It generated a good initial codebase, which I then reviewed and improved

During development, I faced a few real issues.

The biggest issue was inconsistent scoring:
- When I entered the same financial data twice, I sometimes got different scores Like 1st 70/100 Score , 2nd 50/100 Score .
- This was happening because the model response was not fully deterministic and some values were not strictly controlled

To fix this:
- I explain the senario to cursor made the analyzer logic fully deterministic
- Ensured the same input always produces the same output.
- Reduced unnecessary dependency on LLM for calculations
As of now
- session memory is in app
- For better stability, Redis or MongoDB can be used later for persistence.

For quality checks:
- I used Codex to review whether the solution meets all criteria
- It suggested a few improvements, which i tell to uptimize it.
- Then I re tested again in Cursor to confirm everything works properly

Finally I deployed the project on Render.

# SecuFi Saathi - Architecture 

This is a AI insurance assistant project for Indian families.
Main idea is simple:
- chat with user normally
- collect enough family money details
- run gap analysis tool
- explain result in plain language

I kept this project modular so each part is easy to understand.

LLM config I used

`OPENAI_API_KEY=your_openrouter_or_openai_key`  
`OPENAI_MODEL=openai/gpt-4.1-mini`  
`OPENAI_BASE_URL=https://openrouter.ai/api/v1`  
`OPENAI_MAX_TOKENS=1000`

This is OpenAI-compatible setup, so same code works with OpenAI/OpenRouter style endpoints.

---

How the flow works (normal case)

User sends message -> agent reads chat history -> model decides next step.

Next step can be:
- ask missing details
- call gap analysis tool
- call MCP knowledge search
- call web search (only when fresh/current info is needed)

Then tool returns structured JSON and assistant converts it to a simple human answer.

---

Main files

- `src/app.py` - FastAPI API + chat endpoint
- `src/agent.py` - core loop, tool calls, session memory
- `src/tools/gap_analyzer.py` - Round 1 analyzer wrapped as tool
- `src/tools/web_search.py` - current info lookup
- `src/mcp/server.py` - custom MCP server
- `src/knowledge/indian-insurance.md` - insurance knowledge content
- `prompts/system_prompt.md` - behavior + safety rules
- `evals/evals.py` - end-to-end behavior checks

---

Memory and follow-up

Session memory is kept in app memory using `session_id`.
It stores:
- previous messages
- latest report (`last_report`)

So user can ask follow-up like "what about my wife?" without entering everything again.

Tradeoff: if server restarts, memory is gone (not persistent yet).

---

Tool calling style

I am using native tool/function calling from model.
No regex parsing tricks.
Model itself decides when tool should be used.

Gap analyzer tool uses schema-based input/output and gives structured result.

---

MCP usage

Custom MCP server is used for insurance knowledge retrieval.
Reason:
- assignment requires MCP
- keeps long insurance content outside prompt
- easier to update knowledge later

---

Safety behavior

Prompt has clear guardrails.  
Agent should not:
- recommend exact insurer/product SKU
- promise claim approval or guaranteed returns
- give legal/tax/dispute advice

Also it should explain life cover is mostly for income replacement.

---

Why FastAPI

Chose FastAPI because analyzer is already Python and FastAPI keeps backend simple.
It is quick to run locally and easy to deploy.

---

Evals

`evals/evals.py` checks behavior end-to-end (not only formulas), including:
- tool usage
- memory in follow-up questions
- safety response style
- knowledge retrieval
- web search for fresh questions

---

