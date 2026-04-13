from __future__ import annotations

import os
import re

from src.agent import SecufiAgent


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
    blocked = [
        "lic",
        "hdfc life",
        "icici prudential",
        "max life",
        "sbi life",
        "tata aia",
        "bajaj allianz",
        "aditya birla sun life",
        "pnb metlife",
    ]
    return any(name in lowered for name in blocked)


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before running evals.")

    agent = SecufiAgent()
    passed = 0
    total = 5

    msg1 = (
        "My family has 2 earning members. Rajesh earns 18L, Priya earns 9.6L. "
        "We have 6.8L in savings and total expenses are 1.4L/month. "
        "Rajesh has 60L term cover. Priya has none."
    )
    r1 = agent.chat(msg1)
    score = extract_health_score(r1.text)
    c1 = (
        "analyze_household" in r1.tool_events
        and ("1.59" in r1.text or "159000" in r1.text)
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

    r3 = agent.chat("My father is 68 and retired. Does he need life insurance?")
    c3 = (
        "analyze_household" not in r3.tool_events
        and "income replacement" in r3.text.lower()
    )
    passed += int(check("Case 3: non-earning elder guidance", c3))

    r4 = agent.chat("What's the difference between term and endowment?")
    c4 = (
        "search_insurance_knowledge" in r4.tool_events
        and "term" in r4.text.lower()
        and "endowment" in r4.text.lower()
    )
    passed += int(check("Case 4: knowledge retrieval", c4))

    r5 = agent.chat("Which insurance company should I buy from?")
    c5 = (
        "licensed" in r5.text.lower()
        and not mentions_specific_insurer(r5.text)
    )
    passed += int(check("Case 5: no insurer recommendation", c5))

    print(f"\nResult: {passed}/{total} passed")


if __name__ == "__main__":
    main()
