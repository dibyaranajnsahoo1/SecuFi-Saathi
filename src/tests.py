"""
SecuFi Gap Analyzer - test cases.

Run with:
    python tests.py
"""

from __future__ import annotations

import sys
import traceback

from pydantic import ValidationError

from analyzer import analyze_household
from models import SeverityLevel


SHARMA_FAMILY = {
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
                    {"bank": "HDFC Bank", "account_type": "savings", "balance": 185000},
                    {"bank": "SBI", "account_type": "savings", "balance": 62000},
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
                    {"bank": "ICICI Bank", "account_type": "savings", "balance": 94000}
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
                    {"bank": "PNB", "account_type": "savings", "balance": 340000}
                ],
                "life_insurance": [],
            },
        ],
    }
}

ADEQUATE_HOUSEHOLD = {
    "household": {
        "id": "adequate-family",
        "name": "Well-Protected Household",
        "members": [
            {
                "id": "a1",
                "name": "Ananya Mehta",
                "relation": "self",
                "age": 35,
                "is_earning": True,
                "annual_income": 2000000,
                "monthly_expenses": 50000,
                "dependents": 2,
                "bank_balances": [
                    {"bank": "HDFC Bank", "account_type": "savings", "balance": 400000},
                    {"bank": "Axis Bank", "account_type": "savings", "balance": 200000},
                ],
                "life_insurance": [
                    {
                        "provider": "Max Life",
                        "type": "term",
                        "cover_amount": 20000000,
                        "annual_premium": 18000,
                    }
                ],
            },
            {
                "id": "a2",
                "name": "Karan Mehta",
                "relation": "spouse",
                "age": 37,
                "is_earning": True,
                "annual_income": 1500000,
                "monthly_expenses": 50000,
                "dependents": 2,
                "bank_balances": [
                    {"bank": "ICICI Bank", "account_type": "savings", "balance": 300000}
                ],
                "life_insurance": [
                    {
                        "provider": "ICICI Prudential",
                        "type": "term",
                        "cover_amount": 15000000,
                        "annual_premium": 14000,
                    }
                ],
            },
        ],
    }
}

SINGLE_ELDERLY_HOUSEHOLD = {
    "household": {
        "id": "single-elderly",
        "name": "Retired Widow",
        "members": [
            {
                "id": "e1",
                "name": "Kamla Devi",
                "relation": "self",
                "age": 72,
                "is_earning": False,
                "annual_income": 0,
                "monthly_expenses": 18000,
                "dependents": 0,
                "bank_balances": [
                    {"bank": "SBI", "account_type": "savings", "balance": 75000}
                ],
                "life_insurance": [],
            }
        ],
    }
}

EARNING_ZERO_INCOME_HOUSEHOLD = {
    "household": {
        "id": "edge-zero-income",
        "name": "Edge Case Household",
        "members": [
            {
                "id": "z1",
                "name": "Ravi Kumar",
                "relation": "self",
                "age": 30,
                "is_earning": True,
                "annual_income": 0,
                "monthly_expenses": 25000,
                "dependents": 1,
                "bank_balances": [
                    {"bank": "Kotak Bank", "account_type": "savings", "balance": 50000}
                ],
                "life_insurance": [],
            }
        ],
    }
}

ZERO_EXPENSES_HOUSEHOLD = {
    "household": {
        "id": "zero-expenses",
        "name": "Zero Expenses Household",
        "members": [
            {
                "id": "ze1",
                "name": "Deepak Rao",
                "relation": "self",
                "age": 40,
                "is_earning": True,
                "annual_income": 1200000,
                "monthly_expenses": 0,
                "dependents": 0,
                "bank_balances": [],
                "life_insurance": [
                    {
                        "provider": "HDFC Life",
                        "type": "term",
                        "cover_amount": 12000000,
                        "annual_premium": 10000,
                    }
                ],
            }
        ],
    }
}

INVALID_PARTIAL_HOUSEHOLD = {
    "household": {
        "id": "partial-household",
        "name": "Partial Household",
        "members": [
            {
                "id": "p1",
                "name": "Missing Flag Example",
                "relation": "self",
                "age": 28,
                "annual_income": 500000,
                "monthly_expenses": 20000,
                "dependents": 0,
                "bank_balances": [],
                "life_insurance": [],
            }
        ],
    }
}


def assert_close(
    actual: float,
    expected: float,
    label: str,
    tolerance: float = 0.01,
) -> None:
    """Assert two floats are equal within a small tolerance."""

    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"[{label}] Expected {expected}, got {actual} "
            f"(diff={abs(actual - expected):.4f})"
        )


PASS = "[PASS]"
FAIL = "[FAIL]"

passed = 0
failed = 0


def run_test(name: str, fn) -> None:
    global passed, failed

    try:
        fn()
        print(f"  {PASS} {name}")
        passed += 1
    except AssertionError as error:
        print(f"  {FAIL} {name}")
        print(f"         {error}")
        failed += 1
    except Exception:
        print(f"  {FAIL} {name} [EXCEPTION]")
        traceback.print_exc()
        failed += 1


def test_sharma_emergency_fund_totals() -> None:
    report = analyze_household(SHARMA_FAMILY)
    emergency_fund = report.emergency_fund

    assert_close(emergency_fund.total_liquid_savings, 681000, "total_liquid_savings")
    assert_close(
        emergency_fund.total_monthly_expenses,
        140000,
        "total_monthly_expenses",
    )
    assert_close(emergency_fund.required_amount, 840000, "required_amount")


def test_sharma_emergency_fund_gap() -> None:
    report = analyze_household(SHARMA_FAMILY)
    emergency_fund = report.emergency_fund

    assert_close(emergency_fund.gap_amount, 159000, "gap_amount")
    assert_close(emergency_fund.months_covered, 4.9, "months_covered")
    assert emergency_fund.severity == SeverityLevel.WARNING


def test_sharma_rajesh_life_cover() -> None:
    report = analyze_household(SHARMA_FAMILY)
    rajesh = next(cover for cover in report.life_cover if cover.member_id == "m1")

    assert_close(rajesh.annual_income, 1800000, "rajesh.annual_income")
    assert_close(rajesh.required_cover, 18000000, "rajesh.required_cover")
    assert_close(rajesh.existing_cover, 6000000, "rajesh.existing_cover")
    assert_close(rajesh.gap_amount, 12000000, "rajesh.gap_amount")
    assert rajesh.severity == SeverityLevel.CRITICAL


def test_sharma_priya_life_cover() -> None:
    report = analyze_household(SHARMA_FAMILY)
    priya = next(cover for cover in report.life_cover if cover.member_id == "m2")

    assert_close(priya.annual_income, 960000, "priya.annual_income")
    assert_close(priya.required_cover, 9600000, "priya.required_cover")
    assert_close(priya.existing_cover, 0, "priya.existing_cover")
    assert_close(priya.gap_amount, 9600000, "priya.gap_amount")
    assert priya.severity == SeverityLevel.CRITICAL


def test_sharma_non_earners_skipped() -> None:
    report = analyze_household(SHARMA_FAMILY)
    skipped_ids = {member.member_id for member in report.skipped_members}

    assert "m3" in skipped_ids
    assert "m4" in skipped_ids
    assert len(report.life_cover) == 2


def test_sharma_health_score() -> None:
    report = analyze_household(SHARMA_FAMILY)
    assert report.household_health_score == 50


def test_sharma_recommendation_count() -> None:
    report = analyze_household(SHARMA_FAMILY)
    assert 2 <= len(report.recommendations) <= 5


def test_sharma_recommendation_priority() -> None:
    report = analyze_household(SHARMA_FAMILY)
    assert "Priya" in report.recommendations[0]


def test_sharma_metadata() -> None:
    report = analyze_household(SHARMA_FAMILY)

    assert report.metadata.total_members == 4
    assert report.metadata.earning_members_analyzed == 2
    assert report.metadata.members_skipped_from_life_cover == 2
    assert report.metadata.non_earning_members_skipped == 2
    assert report.metadata.zero_income_earners_skipped == 0


def test_adequate_emergency_fund() -> None:
    report = analyze_household(ADEQUATE_HOUSEHOLD)
    emergency_fund = report.emergency_fund

    assert_close(emergency_fund.total_liquid_savings, 900000, "adequate.savings")
    assert_close(emergency_fund.required_amount, 600000, "adequate.required")
    assert_close(emergency_fund.gap_amount, 0, "adequate.gap")
    assert_close(emergency_fund.months_covered, 9.0, "adequate.months")
    assert emergency_fund.severity == SeverityLevel.ADEQUATE


def test_adequate_life_cover_ananya() -> None:
    report = analyze_household(ADEQUATE_HOUSEHOLD)
    ananya = next(cover for cover in report.life_cover if cover.member_id == "a1")

    assert_close(ananya.required_cover, 20000000, "ananya.required_cover")
    assert_close(ananya.existing_cover, 20000000, "ananya.existing_cover")
    assert_close(ananya.gap_amount, 0, "ananya.gap_amount")
    assert ananya.severity == SeverityLevel.ADEQUATE


def test_adequate_life_cover_karan() -> None:
    report = analyze_household(ADEQUATE_HOUSEHOLD)
    karan = next(cover for cover in report.life_cover if cover.member_id == "a2")

    assert_close(karan.required_cover, 15000000, "karan.required_cover")
    assert_close(karan.existing_cover, 15000000, "karan.existing_cover")
    assert_close(karan.gap_amount, 0, "karan.gap_amount")
    assert karan.severity == SeverityLevel.ADEQUATE


def test_adequate_health_score() -> None:
    report = analyze_household(ADEQUATE_HOUSEHOLD)
    assert report.household_health_score == 100


def test_adequate_no_skipped_members() -> None:
    report = analyze_household(ADEQUATE_HOUSEHOLD)
    assert report.metadata.members_skipped_from_life_cover == 0
    assert report.skipped_members == []


def test_elderly_no_life_cover_analysis() -> None:
    report = analyze_household(SINGLE_ELDERLY_HOUSEHOLD)
    assert report.life_cover == []


def test_elderly_skipped_reason() -> None:
    report = analyze_household(SINGLE_ELDERLY_HOUSEHOLD)
    assert len(report.skipped_members) == 1
    assert report.skipped_members[0].member_id == "e1"
    assert "income replacement" in report.skipped_members[0].reason


def test_elderly_emergency_fund() -> None:
    report = analyze_household(SINGLE_ELDERLY_HOUSEHOLD)
    emergency_fund = report.emergency_fund

    assert_close(emergency_fund.total_liquid_savings, 75000, "elderly.savings")
    assert_close(emergency_fund.required_amount, 108000, "elderly.required")
    assert_close(emergency_fund.gap_amount, 33000, "elderly.gap")
    assert emergency_fund.severity == SeverityLevel.WARNING


def test_elderly_health_score() -> None:
    report = analyze_household(SINGLE_ELDERLY_HOUSEHOLD)
    assert report.household_health_score == 90


def test_zero_income_earner_skipped() -> None:
    report = analyze_household(EARNING_ZERO_INCOME_HOUSEHOLD)
    assert len(report.skipped_members) == 1
    assert report.skipped_members[0].member_id == "z1"
    assert "annual_income is zero" in report.skipped_members[0].reason


def test_zero_income_no_life_cover() -> None:
    report = analyze_household(EARNING_ZERO_INCOME_HOUSEHOLD)
    assert report.life_cover == []


def test_zero_income_metadata() -> None:
    report = analyze_household(EARNING_ZERO_INCOME_HOUSEHOLD)
    assert report.metadata.members_skipped_from_life_cover == 1
    assert report.metadata.non_earning_members_skipped == 0
    assert report.metadata.zero_income_earners_skipped == 1


def test_zero_expenses_adequate_emergency_fund() -> None:
    report = analyze_household(ZERO_EXPENSES_HOUSEHOLD)
    emergency_fund = report.emergency_fund

    assert emergency_fund.severity == SeverityLevel.ADEQUATE
    assert_close(emergency_fund.required_amount, 0, "zero_expenses.required")
    assert_close(emergency_fund.gap_amount, 0, "zero_expenses.gap")


def test_zero_expenses_life_cover() -> None:
    report = analyze_household(ZERO_EXPENSES_HOUSEHOLD)
    deepak = report.life_cover[0]

    assert_close(deepak.required_cover, 12000000, "deepak.required_cover")
    assert_close(deepak.existing_cover, 12000000, "deepak.existing_cover")
    assert deepak.severity == SeverityLevel.ADEQUATE


def test_partial_data_is_rejected() -> None:
    try:
        analyze_household(INVALID_PARTIAL_HOUSEHOLD)
    except ValidationError:
        return

    raise AssertionError("Expected ValidationError for missing required input fields")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("\n" + "=" * 60)
    print("  SecuFi Gap Analyzer - Test Suite")
    print("=" * 60)

    suites = [
        (
            "Suite 1: Sharma Family (gaps expected)",
            [
                ("Emergency fund totals correct", test_sharma_emergency_fund_totals),
                ("Emergency fund gap and months covered", test_sharma_emergency_fund_gap),
                ("Rajesh life cover is critical", test_sharma_rajesh_life_cover),
                ("Priya life cover is critical", test_sharma_priya_life_cover),
                ("Non-earners are skipped", test_sharma_non_earners_skipped),
                ("Health score is 50", test_sharma_health_score),
                ("Recommendations count is bounded", test_sharma_recommendation_count),
                ("Zero-cover member is prioritized", test_sharma_recommendation_priority),
                ("Metadata counts are correct", test_sharma_metadata),
            ],
        ),
        (
            "Suite 2: Adequate Household (no gaps)",
            [
                ("Emergency fund is adequate", test_adequate_emergency_fund),
                ("Ananya life cover is adequate", test_adequate_life_cover_ananya),
                ("Karan life cover is adequate", test_adequate_life_cover_karan),
                ("Health score is 100", test_adequate_health_score),
                ("No members are skipped", test_adequate_no_skipped_members),
            ],
        ),
        (
            "Suite 3: Single Elderly Non-Earning Member",
            [
                ("No life cover analysis is created", test_elderly_no_life_cover_analysis),
                ("Skipped reason explains why", test_elderly_skipped_reason),
                ("Emergency fund is warning", test_elderly_emergency_fund),
                ("Health score is 90", test_elderly_health_score),
            ],
        ),
        (
            "Suite 4: Earning Member with Zero Income",
            [
                ("Zero-income earner is skipped", test_zero_income_earner_skipped),
                ("No life cover entry is created", test_zero_income_no_life_cover),
                ("Metadata separates skip reasons", test_zero_income_metadata),
            ],
        ),
        (
            "Suite 5: Zero Monthly Expenses",
            [
                ("Emergency fund stays adequate", test_zero_expenses_adequate_emergency_fund),
                ("Life cover still analyzed", test_zero_expenses_life_cover),
            ],
        ),
        (
            "Suite 6: Partial Data Validation",
            [("Incomplete input is rejected", test_partial_data_is_rejected)],
        ),
    ]

    for suite_name, suite_tests in suites:
        print(f"\n{suite_name}")
        print("-" * 50)
        for test_name, test_fn in suite_tests:
            run_test(test_name, test_fn)

    print("\n" + "=" * 60)
    total = passed + failed
    print(f"  Results: {passed}/{total} passed", end="")
    if failed == 0:
        print(" - ALL TESTS PASSED")
    else:
        print(f" - {failed} FAILED")
    print("=" * 60 + "\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
