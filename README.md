# SecuFi Saathi (Round 2)

SecuFi Saathi is a conversational AI assistant for Indian households. The user shares family finances naturally in chat, the agent decides when to run gap analysis, and then explains the result in simple Indian English with practical next steps.

This build is intentionally focused on trust and clarity: structured tool usage, strict safety guardrails, follow-up memory, and transparent documentation.

## What I optimized for
- A useful response for a real Indian family in the first few turns.
- Clean agent architecture that is easy to inspect during review.
- Safety-first behavior when users ask recommendation-style questions.
- Reproducible evaluation results that map directly to the rubric.

## Live URL
- Deployed URL: `TODO_ADD_DEPLOYED_URL`
- If URL is not ready at submission time, include a short screen recording link in this section.

## Requirement mapping
- **R1 LLM integration:** `src/agent.py` uses native OpenAI-style tool calling (`tool_choice="auto"`) with session memory.
- **R2 Gap analyzer tool:** `src/tools/gap_analyzer.py` exposes Round 1 analysis via structured schema in tool definitions.
- **R3 Web search tool (optional + implemented):** `src/tools/web_search.py` (DDGS web search).
- **R4 Knowledge skill:** `src/knowledge/indian-insurance.md` queried by MCP tool `search_insurance_knowledge`.
- **R5 MCP integration:** custom MCP server at `src/mcp/server.py` (stdio transport).
- **R6 Evaluation:** `evals/evals.py` includes 6 behavior-level checks with pass/fail output.

## Project structure
- `src/agent.py` - main orchestration loop and conversation memory
- `src/app.py` - FastAPI API and minimal web UI hosting
- `src/tools/gap_analyzer.py` - Round 1 analyzer tool wrapper
- `src/tools/web_search.py` - web search tool
- `src/mcp/server.py` - custom MCP knowledge server
- `src/knowledge/indian-insurance.md` - insurance educational knowledge base
- `src/prompts/system_prompt.md` - agent system prompt
- `evals/evals.py` - end-to-end evaluation script
- `evals/results.md` - latest eval run output snapshot
- `ARCHITECTURE.md` - design choices and tradeoffs
- `CLAUDE.md` - build context and constraints

## How a real chat works
1. User shares household details in free text.
2. Agent extracts structured fields and decides if it already has enough data.
3. If enough data exists, agent calls `analyze_household`.
4. Agent explains emergency-fund gap, life-cover gaps, and priorities in plain language.
5. Follow-up questions (for example "What about Priya?") reuse session context without asking everything again.

## Reviewer quick-start (2 minutes)
1. Run `python -m uvicorn src.app:app --reload`.
2. Open `http://127.0.0.1:8000`.
3. Paste the sample household scenario from the assignment.
4. Ask two follow-ups: `Is Priya covered?` and `Which insurance company should I buy from?`.
5. Confirm the agent remembers context and avoids specific insurer recommendations.

## Local setup
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Fill `.env`:
```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=openai/gpt-4.1-mini
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MAX_TOKENS=1200
```

## Run locally
```bash
python -m uvicorn src.app:app --reload
```

Open: `http://127.0.0.1:8000`

UI behavior:
- user messages appear as **You**
- assistant messages appear as **SecuFi Saathi**

## Run checks
Round 1 analyzer tests:
```bash
python src/tests.py
```

Round 2 agent evals:
```bash
python evals/evals.py
```

Expected eval status:
- `Result: 6/6 passed` (see `evals/results.md`)

Current eval coverage includes:
- gap-analysis tool usage + score/gap output checks
- follow-up memory behavior
- retired parent safety guidance
- knowledge retrieval route usage
- no specific insurer recommendation
- web freshness query route usage

## Deploy on Render (recommended)
1. Push repo to GitHub.
2. In Render, create **Web Service** from the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn src.app:app --host 0.0.0.0 --port $PORT`
5. Set environment variables:
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `OPENAI_BASE_URL`
   - `OPENAI_MAX_TOKENS`
6. Deploy and copy generated URL into this README.

`render.yaml` is included for infrastructure-as-code style setup.

## Deploy on Vercel
1. Import the repo in Vercel.
2. Use `vercel.json` included in repo.
3. Add environment variables:
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `OPENAI_BASE_URL`
   - `OPENAI_MAX_TOKENS`
4. Deploy and verify `GET /` and `POST /api/chat`.

## Security note
- Never commit real API keys.
- Keep only placeholder values in `.env.example`.

## Known limitations (honest notes)
- Session memory is in-process and resets on restart.
- Web results depend on live internet and source availability.
- This assistant is educational and not a substitute for licensed financial, tax, or legal advice.
