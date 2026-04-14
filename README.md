# SecuFi Saathi

SecuFi Saathi is a conversational AI assistant for Indian households. A user shares family details in natural language, the agent decides when to call the gap analyzer tool, and then explains emergency fund and life cover gaps in plain Indian English.

## Live URL
- Deployed URL: `ADD_YOUR_DEPLOYED_URL_HERE`

## Requirement Mapping
- **R1 - LLM integration:** `src/agent.py` uses native function/tool calling with conversation memory (`session_id` based).
- **R2 - Gap analyzer tool:** `src/tools/gap_analyzer.py` wraps Round 1 analyzer and returns structured report output.
- **R3 - Web search tool (optional):** `src/tools/web_search.py` enables current-info lookup flow.
- **R4 - Knowledge skill:** insurance education content in `src/knowledge/indian-insurance.md` is served via MCP tool.
- **R5 - MCP integration:** custom MCP server in `src/mcp/server.py` exposes `search_insurance_knowledge`.
- **R6 - Evaluation:** `evals/evals.py` runs 5 end-to-end behavior checks and prints pass/fail.

## Repository Structure
- `src/agent.py` - agent loop, memory, tool routing
- `src/app.py` - FastAPI app and chat API
- `src/tools/gap_analyzer.py` - Round 1 analyzer tool wrapper
- `src/tools/web_search.py` - optional freshness tool
- `src/mcp/server.py` - custom MCP server
- `src/knowledge/indian-insurance.md` - knowledge base
- `src/prompts/system_prompt.md` - system prompt
- `evals/evals.py` - eval runner
- `evals/results.md` - paste eval output
- `ARCHITECTURE.md` - architecture decisions and tradeoffs
- `REFLECTION.md` - implementation journey and debugging notes
- `CLAUDE.md` - project context/instructions

## Quick Local Run
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn src.app:app --reload
```

Open `http://127.0.0.1:8000`.

## Environment Variables
Add these in `.env`:

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=openai/gpt-4.1-mini
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MAX_TOKENS=1200
```

## Tests and Evals
Round 1 regression tests:
```bash
python src/tests.py
```

Round 2 behavior evals:
```bash
python evals/evals.py
```

Eval coverage includes:
- tool-call behavior for analysis
- follow-up memory ("Is Priya covered?")
- non-earning retired parent safety response
- knowledge retrieval behavior
- no specific insurer recommendation

## Deploy on Render (recommended)
1. Push this repo to GitHub.
2. Create a new Render **Web Service**.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn src.app:app --host 0.0.0.0 --port $PORT`
5. Add env vars:
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `OPENAI_BASE_URL`
   - `OPENAI_MAX_TOKENS`
6. Deploy and place URL in the Live URL section.

`render.yaml` is already included.

## Deploy on Vercel
1. Import this repo in Vercel.
2. Keep `vercel.json` from the repo root.
3. Add the same env vars used above.
4. Deploy and verify:
   - `GET /`
   - `POST /api/chat`

## Security
- Do not commit real keys.
- `.env` is ignored via `.gitignore`.
- Keep placeholders only in `.env.example`.

## Known Limitations
- Session memory is in-process and resets on app restart.
- Knowledge retrieval is lightweight keyword matching via MCP tool.
- Assistant is educational support, not licensed financial/tax/legal advice.
