"""
SecuFi Gap Analyzer - core analysis engine.

Pure function:
    analyze_household(household_data: dict) -> GapReport
"""

from __future__ import annotations

import json
import math
from datetime import date

from models import (
    AnalysisMetadata,
    EmergencyFundAnalysis,
    GapReport,
    HouseholdInput,
    HouseholdMember,
    LifeCoverAnalysis,
    SeverityLevel,
    SkippedMember,
)


def format_inr(amount: float) -> str:
    """
    Format a number using Indian financial notation.

    - Below 1,00,000  -> rupee format with commas
    - 1,00,000+       -> lakh
    - 1,00,00,000+    -> crore
    """

    if amount < 0:
        return f"-{format_inr(-amount)}"
    if amount >= 1_00_00_000:
        return f"₹{amount / 1_00_00_000:.2f} crore"
    if amount >= 1_00_000:
        return f"₹{amount / 1_00_000:.2f} lakh"
    return f"₹{amount:,.0f}"


def _analyze_emergency_fund(members: list[HouseholdMember]) -> EmergencyFundAnalysis:
    """Aggregate all members' expenses and bank balances."""

    total_monthly_expenses = sum(member.monthly_expenses for member in members)
    total_liquid_savings = sum(
        balance.balance
        for member in members
        for balance in member.bank_balances
    )
    required_amount = total_monthly_expenses * 6

    if total_monthly_expenses == 0:
        return EmergencyFundAnalysis(
            total_liquid_savings=total_liquid_savings,
            total_monthly_expenses=0.0,
            required_amount=0.0,
            gap_amount=0.0,
            months_covered=float("inf"),
            severity=SeverityLevel.ADEQUATE,
            explanation=(
                "Your household has no recorded monthly expenses, so the "
                "emergency fund is treated as adequate for this analysis."
            ),
        )

    months_covered = round(total_liquid_savings / total_monthly_expenses, 1)
    gap_amount = max(0.0, required_amount - total_liquid_savings)

    if months_covered >= 6:
        severity = SeverityLevel.ADEQUATE
    elif months_covered >= 3:
        severity = SeverityLevel.WARNING
    else:
        severity = SeverityLevel.CRITICAL

    savings_fmt = format_inr(total_liquid_savings)
    required_fmt = format_inr(required_amount)
    gap_fmt = format_inr(gap_amount)

    if severity == SeverityLevel.ADEQUATE:
        explanation = (
            f"Your household has {savings_fmt} in liquid savings, which covers "
            f"{months_covered} months of expenses. That meets the recommended "
            f"6-month buffer of {required_fmt}."
        )
    elif severity == SeverityLevel.WARNING:
        explanation = (
            f"Your family has about {months_covered} months of expenses covered "
            f"({savings_fmt} saved). The recommended buffer is 6 months "
            f"({required_fmt}), so you are short by about {gap_fmt}."
        )
    else:
        explanation = (
            f"Your household currently has only {months_covered} months of "
            f"expenses covered ({savings_fmt} in liquid savings). The "
            f"recommended 6-month buffer is {required_fmt}, leaving a critical "
            f"shortfall of {gap_fmt}."
        )

    return EmergencyFundAnalysis(
        total_liquid_savings=total_liquid_savings,
        total_monthly_expenses=total_monthly_expenses,
        required_amount=required_amount,
        gap_amount=gap_amount,
        months_covered=months_covered,
        severity=severity,
        explanation=explanation,
    )


def _analyze_life_cover(
    members: list[HouseholdMember],
) -> tuple[list[LifeCoverAnalysis], list[SkippedMember]]:
    """
    Analyze life cover only for members where:
    is_earning is True and annual_income is greater than zero.
    """

    analyses: list[LifeCoverAnalysis] = []
    skipped: list[SkippedMember] = []

    for member in members:
        if not member.is_earning:
            skipped.append(
                SkippedMember(
                    member_id=member.id,
                    member_name=member.name,
                    reason=(
                        "Non-earning member - life insurance is for income "
                        "replacement only."
                    ),
                )
            )
            continue

        if member.annual_income == 0:
            skipped.append(
                SkippedMember(
                    member_id=member.id,
                    member_name=member.name,
                    reason=(
                        "Marked as earning but annual_income is zero. "
                        "Required life cover cannot be computed without income data."
                    ),
                )
            )
            continue

        existing_cover = sum(policy.cover_amount for policy in member.life_insurance)
        required_cover = member.annual_income * 10
        gap_amount = max(0.0, required_cover - existing_cover)

        if gap_amount == 0:
            severity = SeverityLevel.ADEQUATE
        elif existing_cover == 0 or gap_amount > member.annual_income * 5:
            severity = SeverityLevel.CRITICAL
        else:
            severity = SeverityLevel.WARNING

        first_name = member.name.split()[0]
        income_fmt = format_inr(member.annual_income)
        required_fmt = format_inr(required_cover)
        existing_fmt = format_inr(existing_cover)
        gap_fmt = format_inr(gap_amount)

        if member.dependents > 0:
            dependent_clause = (
                f"with {member.dependents} dependent"
                f"{'s' if member.dependents != 1 else ''}"
            )
        else:
            dependent_clause = "even without listed dependents"

        if severity == SeverityLevel.ADEQUATE:
            explanation = (
                f"{first_name} has {existing_fmt} in life cover, which meets or "
                f"exceeds the recommended {required_fmt} (10x annual income of "
                f"{income_fmt})."
            )
        elif severity == SeverityLevel.CRITICAL and existing_cover == 0:
            explanation = (
                f"{first_name} has no life insurance at all. {dependent_clause.capitalize()}, "
                f"a cover of at least {required_fmt} (10x annual income of {income_fmt}) "
                f"is strongly recommended."
            )
        elif severity == SeverityLevel.CRITICAL:
            explanation = (
                f"{first_name} has {existing_fmt} in life cover but needs about "
                f"{required_fmt} (10x annual income of {income_fmt}) {dependent_clause}. "
                f"The gap of {gap_fmt} is significant."
            )
        else:
            explanation = (
                f"{first_name} has {existing_fmt} in life cover against a recommended "
                f"{required_fmt}. The gap of {gap_fmt} {dependent_clause} should be addressed."
            )

        analyses.append(
            LifeCoverAnalysis(
                member_id=member.id,
                member_name=member.name,
                annual_income=member.annual_income,
                required_cover=required_cover,
                existing_cover=existing_cover,
                gap_amount=gap_amount,
                severity=severity,
                explanation=explanation,
            )
        )

    return analyses, skipped


def _compute_health_score(
    emergency_fund: EmergencyFundAnalysis,
    life_covers: list[LifeCoverAnalysis],
) -> int:
    """Compute a simple 0-100 household protection score."""

    score = 100

    if emergency_fund.severity == SeverityLevel.CRITICAL:
        score -= 25
    elif emergency_fund.severity == SeverityLevel.WARNING:
        score -= 10

    for life_cover in life_covers:
        if life_cover.severity == SeverityLevel.CRITICAL:
            score -= 20
        elif life_cover.severity == SeverityLevel.WARNING:
            score -= 10

    return max(0, min(100, score))


def _build_recommendations(
    emergency_fund: EmergencyFundAnalysis,
    life_covers: list[LifeCoverAnalysis],
) -> list[str]:
    """Generate up to five prioritized recommendations."""

    recommendations: list[str] = []

    critical_covers = sorted(
        [cover for cover in life_covers if cover.severity == SeverityLevel.CRITICAL],
        key=lambda cover: (cover.existing_cover > 0, -cover.gap_amount),
    )
    warning_covers = sorted(
        [cover for cover in life_covers if cover.severity == SeverityLevel.WARNING],
        key=lambda cover: cover.gap_amount,
        reverse=True,
    )

    for cover in critical_covers:
        if len(recommendations) >= 5:
            break

        name = cover.member_name.split()[0]
        gap_fmt = format_inr(cover.gap_amount)
        required_fmt = format_inr(cover.required_cover)

        if cover.existing_cover == 0:
            recommendations.append(
                f"Top priority: {name} currently has zero life cover. "
                f"A pure term insurance plan for at least {required_fmt} is the "
                f"most cost-effective way to protect your family's income."
            )
        else:
            recommendations.append(
                f"{name}'s life cover gap of {gap_fmt} is substantial. Consider "
                f"a top-up term plan to bring total cover closer to the "
                f"recommended {required_fmt}."
            )

    for cover in warning_covers:
        if len(recommendations) >= 5:
            break

        name = cover.member_name.split()[0]
        gap_fmt = format_inr(cover.gap_amount)
        recommendations.append(
            f"{name}'s life cover has a moderate gap of {gap_fmt}. Reviewing "
            f"existing policies and adding more cover would improve income "
            f"protection for your family."
        )

    if len(recommendations) < 5 and emergency_fund.severity != SeverityLevel.ADEQUATE:
        gap_fmt = format_inr(emergency_fund.gap_amount)
        monthly_top_up = math.ceil(emergency_fund.gap_amount / 12 / 1000) * 1000
        monthly_fmt = format_inr(monthly_top_up)
        months_to_close = (
            math.ceil(emergency_fund.gap_amount / monthly_top_up)
            if monthly_top_up > 0
            else "several"
        )

        if emergency_fund.severity == SeverityLevel.CRITICAL:
            recommendations.append(
                f"Your emergency fund is critically low and short by {gap_fmt}. "
                f"Building a liquid savings buffer should be an immediate priority. "
                f"A monthly contribution of {monthly_fmt} would close this gap in "
                f"about {months_to_close} months."
            )
        else:
            recommendations.append(
                f"Your emergency fund is close to the target but still short by "
                f"{gap_fmt}. A recurring monthly contribution of {monthly_fmt} "
                f"would close this gap in about {months_to_close} months."
            )

    if not recommendations:
        recommendations.append(
            "Your household's financial protection looks strong across the core "
            "areas in this analysis. Review your coverage annually and after any "
            "major life event."
        )

    return recommendations


def analyze_household(household_data: dict) -> GapReport:
    """
    Analyze a household's financial protection gaps.

    Args:
        household_data: Raw dict matching the HouseholdInput schema.

    Returns:
        GapReport with emergency fund analysis, per-member life cover
        analysis, recommendations, and a household health score.
    """

    parsed = HouseholdInput.model_validate(household_data)
    household = parsed.household
    members = household.members

    emergency_fund = _analyze_emergency_fund(members)
    life_cover_analyses, skipped_members = _analyze_life_cover(members)
    health_score = _compute_health_score(emergency_fund, life_cover_analyses)
    recommendations = _build_recommendations(emergency_fund, life_cover_analyses)

    non_earning_members_skipped = sum(1 for member in members if not member.is_earning)
    zero_income_earners_skipped = sum(
        1 for member in members if member.is_earning and member.annual_income == 0
    )

    return GapReport(
        household_id=household.id,
        household_name=household.name,
        analysis_date=date.today().isoformat(),
        household_health_score=health_score,
        emergency_fund=emergency_fund,
        life_cover=life_cover_analyses,
        skipped_members=skipped_members,
        recommendations=recommendations,
        metadata=AnalysisMetadata(
            total_members=len(members),
            earning_members_analyzed=len(life_cover_analyses),
            members_skipped_from_life_cover=len(skipped_members),
            non_earning_members_skipped=non_earning_members_skipped,
            zero_income_earners_skipped=zero_income_earners_skipped,
        ),
    )


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as handle:
            input_data = json.load(handle)
    else:
        input_data = {
            "household": {
                "id": "sharma-family",
                "name": "Sharma Household",
                "members": [
                    {
                        "id": "m1",
                        "name": "Rajesh Sharma",
                        "relation": "self",
                        "age": 42,
                        "is_earning": True,
                        "annual_income": 1800000,
                        "monthly_expenses": 65000,
                        "dependents": 3,
                        "bank_balances": [
                            {
                                "bank": "HDFC Bank",
                                "account_type": "savings",
                                "balance": 185000,
                            },
                            {
                                "bank": "SBI",
                                "account_type": "savings",
                                "balance": 62000,
                            },
                        ],
                        "life_insurance": [
                            {
                                "provider": "HDFC Life",
                                "type": "term",
                                "cover_amount": 5000000,
                                "annual_premium": 12500,
                            },
                            {
                                "provider": "LIC",
                                "type": "endowment",
                                "cover_amount": 1000000,
                                "annual_premium": 45000,
                            },
                        ],
                    },
                    {
                        "id": "m2",
                        "name": "Priya Sharma",
                        "relation": "spouse",
                        "age": 38,
                        "is_earning": True,
                        "annual_income": 960000,
                        "monthly_expenses": 40000,
                        "dependents": 2,
                        "bank_balances": [
                            {
                                "bank": "ICICI Bank",
                                "account_type": "savings",
                                "balance": 94000,
                            }
                        ],
                        "life_insurance": [],
                    },
                    {
                        "id": "m3",
                        "name": "Arjun Sharma",
                        "relation": "son",
                        "age": 16,
                        "is_earning": False,
                        "annual_income": 0,
                        "monthly_expenses": 15000,
                        "dependents": 0,
                        "bank_balances": [],
                        "life_insurance": [],
                    },
                    {
                        "id": "m4",
                        "name": "Suman Sharma",
                        "relation": "father",
                        "age": 68,
                        "is_earning": False,
                        "annual_income": 0,
                        "monthly_expenses": 20000,
                        "dependents": 0,
                        "bank_balances": [
                            {
                                "bank": "PNB",
                                "account_type": "savings",
                                "balance": 340000,
                            }
                        ],
                        "life_insurance": [],
                    },
                ],
            }
        }

    report = analyze_household(input_data)
    print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))
