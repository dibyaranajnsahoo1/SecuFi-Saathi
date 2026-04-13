from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_PATH = BASE_DIR / "knowledge" / "indian-insurance.md"

mcp = FastMCP("secufi-knowledge-server")


def _load_knowledge() -> str:
    return KNOWLEDGE_PATH.read_text(encoding="utf-8")


@mcp.tool()
def search_insurance_knowledge(query: str) -> dict:
    """Return relevant Indian insurance basics snippets for a user query."""
    text = _load_knowledge()
    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    q_words = {word.lower() for word in query.split() if len(word) >= 3}

    scored: list[tuple[int, str]] = []
    for chunk in chunks:
        lowered = chunk.lower()
        score = sum(1 for word in q_words if word in lowered)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    top = [snippet for _, snippet in scored[:4]]

    return {
        "query": query,
        "matched_snippets": top,
        "source": str(KNOWLEDGE_PATH),
    }


if __name__ == "__main__":
    mcp.run()
