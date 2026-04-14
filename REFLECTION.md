# SecuFi Saathi - Reflection

I built this Round 2 project mainly with Cursor as my coding workflow, using my Round 1 analyzer as the base. Instead of trying to rewrite everything manually, I worked in an iterative way: I gave Cursor one clear instruction at a time, verified the output, then asked it to improve specific areas.

My first prompt was basically: "Round 1 logic is done, now build Round 2 around it." I asked Cursor to create the full agent structure from the problem statement, including:
- agent orchestration
- tool calling for the gap analyzer
- knowledge handling for insurance basics
- MCP integration
- evaluation script
- deployment-ready project layout

The initial generated structure was good, but real issues came during runtime. I repeatedly tested through the local UI and terminal, then gave Cursor focused corrective prompts. A few examples of practical prompts I gave during development:
- "Fix import path errors when running uvicorn from root."
- "Do not crash on tool call if arguments are missing."
- "Make OpenRouter work with base URL and model from env."
- "Add max token limit to prevent OpenRouter 402 credit errors."
- "Improve UI: show You and SecuFi Saathi labels and typing indicator."

One major issue I faced was consistency and stability. Earlier, with the same kind of input, outputs could vary and sometimes caused confusion around score interpretation. To reduce this, I made sure that all financial calculations stay deterministic inside the analyzer, and that the LLM is used for orchestration and explanation, not for arithmetic decisions.

Another important fix was robustness of tool execution. At one point the model triggered `analyze_household` without `household_data`, which caused a 500 error. I asked Cursor to harden the tool-call path with defensive checks and graceful fallback messages so the app asks for missing details instead of crashing.

For quality verification, I used both automated and manual checks:
- Round 1 tests to ensure no regression in core logic
- Round 2 behavioral evals for tool use, memory, safety, and knowledge
- repeated manual chat tests in browser for real conversation flow

As of now:
- Session memory works in-app using `session_id` and in-memory state.
- The agent can handle follow-up queries like "What about Priya?" without re-entering all data.
- For production-scale persistence, Redis or MongoDB would be the next upgrade.

Finally, I pushed the code to GitHub and prepared deployment flow for Render/Vercel.  
Overall, Cursor helped me move fast, but I still had to review every important change manually. My main learning: AI is excellent for speed and scaffolding, but production-quality behavior comes from iterative testing, targeted prompts, and human validation.
