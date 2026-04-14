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
    reported_member_expenses = sum(member.monthly_expenses for member in tool_input.members)
    unallocated_expenses = max(0.0, tool_input.total_monthly_expenses - reported_member_expenses)
    no_member_expenses_provided = reported_member_expenses == 0

    reported_member_savings = sum(
        float(balance.get("balance", 0) or 0)
        for member in tool_input.members
        for balance in member.bank_balances
        if isinstance(balance, dict)
    )
    unallocated_savings = max(0.0, tool_input.total_liquid_savings - reported_member_savings)
    no_member_savings_provided = reported_member_savings == 0

    for index, member in enumerate(tool_input.members, start=1):
        member_expenses = member.monthly_expenses
        if index == 1:
            if no_member_expenses_provided and tool_input.total_monthly_expenses > 0:
                member_expenses = tool_input.total_monthly_expenses
            elif unallocated_expenses > 0:
                member_expenses += unallocated_expenses

        bank_balances = list(member.bank_balances)
        if index == 1:
            if no_member_savings_provided and tool_input.total_liquid_savings > 0:
                bank_balances.append(
                    {
                        "bank": "Household pooled savings",
                        "account_type": "savings",
                        "balance": tool_input.total_liquid_savings,
                    }
                )
            elif unallocated_savings > 0:
                bank_balances.append(
                    {
                        "bank": "Household pooled savings (unallocated)",
                        "account_type": "savings",
                        "balance": unallocated_savings,
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
