from __future__ import annotations
from src.agent import SecufiAgent

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def check(name: str, condition: bool) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    return condition


def extract_health_score(text: str) -> int | None:
    """
    Extract score from phrases like:
    - "health score: 38"
    - "overall score is 42 out of 100"
    """
    patterns = [
        r"health\s*score[^0-9]*(\d{1,3})",
        r"score[^0-9]*(\d{1,3})\s*(?:/|out\s+of)\s*100",
    ]
    lowered = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            value = int(match.group(1))
            if 0 <= value <= 100:
                return value
    return None


def mentions_specific_insurer(text: str) -> bool:
    lowered = text.lower()
    blocked_patterns = [
        r"\blic\b",
        r"\bhdfc life\b",
        r"\bicici prudential\b",
        r"\bmax life\b",
        r"\bsbi life\b",
        r"\btata aia\b",
        r"\bbajaj allianz\b",
        r"\baditya birla sun life\b",
        r"\bpnb metlife\b",
    ]
    return any(re.search(pattern, lowered) for pattern in blocked_patterns)


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before running evals.")

    agent = SecufiAgent()
    passed = 0
    total = 8

    msg1 = (
        "My family has 2 earning members. Rajesh earns 18L, Priya earns 9.6L. "
        "We have 6.8L in savings and total expenses are 1.4L/month. "
        "Rajesh has 60L term cover. Priya has none."
    )
    r1 = agent.chat(msg1)
    score = extract_health_score(r1.text)
    c1 = (
        "analyze_household" in r1.tool_events
        and (
            "1.59" in r1.text
            or "1.60" in r1.text
            or "159000" in r1.text
            or "160000" in r1.text
        )
        and "Priya" in r1.text
        and score is not None
        and 30 <= score <= 50
    )
    passed += int(check("Case 1: tool call + gaps + score range", c1))

    r2 = agent.chat("Is Priya covered?", session_id=r1.session_id)
    c2 = (
        "Priya" in r2.text
        and "analyze_household" not in r2.tool_events
        and "share" not in r2.text.lower()
    )
    passed += int(check("Case 2: follow-up memory", c2))

    r3 = agent.chat(
        "My father is 68 and retired. Does he need life insurance?")
    c3 = (
        "analyze_household" not in r3.tool_events
        and "income replacement" in r3.text.lower()
    )
    passed += int(check("Case 3: non-earning elder guidance", c3))

    r4 = agent.chat("What's the difference between term and endowment?")
    c4 = (
        "search_insurance_knowledge" in r4.tool_events
        and "analyze_household" not in r4.tool_events
        and "term" in r4.text.lower()
        and "endowment" in r4.text.lower()
    )
    passed += int(check("Case 4: knowledge retrieval", c4))

    r5 = agent.chat("Which insurance company should I buy from?")
    c5 = (
        "licensed" in r5.text.lower()
        and "analyze_household" not in r5.tool_events
        and not mentions_specific_insurer(r5.text)
    )
    passed += int(check("Case 5: no insurer recommendation", c5))

    r6 = agent.chat("What's the latest IRDAI regulation on free-look period?")
    c6 = (
        "web_search" in r6.tool_events
        and "search_insurance_knowledge" not in r6.tool_events
        and "analyze_household" not in r6.tool_events
        and ("irdai" in r6.text.lower() or "free-look" in r6.text.lower() or "free look" in r6.text.lower())
    )
    passed += int(check("Case 6: freshness query uses web search", c6))

    r7 = agent.chat("What about Priya?", session_id=r1.session_id)
    c7 = (
        "Priya" in r7.text
        and "analyze_household" not in r7.tool_events
        and ("gap" in r7.text.lower() or "cover" in r7.text.lower())
    )
    passed += int(check("Case 7: shorthand follow-up uses memory", c7))

    r8 = agent.chat(
        "Update: Priya now has Rs. 50 lakh term cover and our savings are Rs. 8 lakh. Please recheck.",
        session_id=r1.session_id,
    )
    c8 = (
        "analyze_household" in r8.tool_events
        and ("Priya" in r8.text or "health score" in r8.text.lower())
    )
    passed += int(check("Case 8: updated numbers trigger re-analysis", c8))

    print(f"\nResult: {passed}/{total} passed")


if __name__ == "__main__":
    main()
