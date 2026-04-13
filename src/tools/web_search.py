from __future__ import annotations

from typing import Any

from ddgs import DDGS


def run_web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search current web data (optional tool for freshness checks)."""
    with DDGS() as ddgs:
        rows = list(ddgs.text(query, max_results=max_results))

    results = [
        {
            "title": row.get("title", ""),
            "url": row.get("href", ""),
            "snippet": row.get("body", ""),
        }
        for row in rows
    ]
    return {"query": query, "results": results}
