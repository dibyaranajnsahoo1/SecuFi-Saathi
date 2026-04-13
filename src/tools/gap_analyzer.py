from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

try:
    from analyzer import analyze_household
except ImportError:
    from src.analyzer import analyze_household


class ToolPolicyInput(BaseModel):
    provider: str = Field(default="User reported")
    type: str = Field(default="reported")
    cover_amount: float = Field(ge=0)
    annual_premium: float = Field(default=0, ge=0)


class ToolMemberInput(BaseModel):
    name: str = Field(min_length=1)
    is_earning: bool = True
    annual_income: float = Field(default=0, ge=0)
    existing_cover_amount: float = Field(
        default=0,
        ge=0,
        description="Total current life cover amount if detailed policies are not known.",
    )
    monthly_expenses: float = Field(default=0, ge=0)
    dependents: int = Field(default=0, ge=0)
    relation: str = Field(default="member")
    age: int = Field(default=0, ge=0, le=120)
    life_insurance: list[ToolPolicyInput] = Field(default_factory=list)
    bank_balances: list[dict[str, Any]] = Field(default_factory=list)


class GapAnalyzerToolInput(BaseModel):
    household_name: str = Field(
        default="Household",
        description="Friendly household name for the report.",
    )
    household_id: str = Field(
        default="chat-household",
        description="Stable identifier for the household.",
    )
    total_monthly_expenses: float = Field(
        ge=0,
        description="Total household monthly expenses across all members.",
    )
    total_liquid_savings: float = Field(
        ge=0,
        description="Total liquid savings across bank accounts.",
    )
    members: list[ToolMemberInput] = Field(
        min_length=1,
        description="Known household members relevant to life-cover analysis.",
    )


def get_gap_analyzer_schema() -> dict[str, Any]:
    return GapAnalyzerToolInput.model_json_schema()


def _normalize_policies(member: ToolMemberInput) -> list[dict[str, Any]]:
    if member.life_insurance:
        return [policy.model_dump() for policy in member.life_insurance]
    if member.existing_cover_amount > 0:
        return [
            {
                "provider": "User reported",
                "type": "reported",
                "cover_amount": member.existing_cover_amount,
                "annual_premium": 0,
            }
        ]
    return []


def _normalize_members(tool_input: GapAnalyzerToolInput) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    remaining_expenses = tool_input.total_monthly_expenses
    remaining_savings = tool_input.total_liquid_savings

    for index, member in enumerate(tool_input.members, start=1):
        member_expenses = member.monthly_expenses
        if index == 1 and remaining_expenses > member_expenses:
            member_expenses = remaining_expenses

        bank_balances = list(member.bank_balances)
        if index == 1 and remaining_savings > 0:
            bank_balances.append(
                {
                    "bank": "Household pooled savings",
                    "account_type": "savings",
                    "balance": remaining_savings,
                }
            )

        normalized_member = {
            "id": f"member-{index}",
            "name": member.name,
            "relation": member.relation,
            "age": member.age,
            "is_earning": member.is_earning,
            "annual_income": member.annual_income,
            "monthly_expenses": member_expenses,
            "dependents": member.dependents,
            "bank_balances": bank_balances,
            "life_insurance": _normalize_policies(member),
        }
        members.append(normalized_member)

        remaining_expenses = max(0.0, remaining_expenses - member_expenses)
        remaining_savings = 0.0

    return members


def _normalize_input(payload: dict[str, Any]) -> dict[str, Any]:
    if "household" in payload:
        return payload

    tool_input = GapAnalyzerToolInput.model_validate(payload)
    return {
        "household": {
            "id": tool_input.household_id,
            "name": tool_input.household_name,
            "members": _normalize_members(tool_input),
        }
    }


def run_gap_analysis(household_data: dict[str, Any]) -> dict[str, Any]:
    """Wrapper around Round 1 analyzer for tool use."""
    normalized = _normalize_input(household_data)
    report = analyze_household(normalized)
    return report.model_dump()
