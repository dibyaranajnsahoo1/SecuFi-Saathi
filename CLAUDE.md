# CLAUDE.md - SecuFi Emergency Fund and Life Cover Gap Analyzer

## Goal
Build a pure-Python analyzer for one household JSON payload. The analyzer must:

1. Measure emergency fund adequacy for the full household.
2. Measure life cover adequacy for each earning member.
3. Return a structured gap report with plain-language explanations.

The analyzer should be deterministic. If required structural fields are missing, fail validation rather than guessing.

---

## 1. Input Schema

The input is a single JSON object shaped like this:

```json
{
  "household": {
    "id": "string",
    "name": "string",
    "members": [
      {
        "id": "string",
        "name": "string",
        "relation": "string",
        "age": "integer",
        "is_earning": "boolean",
        "annual_income": "float",
        "monthly_expenses": "float",
        "dependents": "integer",
        "bank_balances": [
          {
            "bank": "string",
            "account_type": "string",
            "balance": "float"
          }
        ],
        "life_insurance": [
          {
            "provider": "string",
            "type": "string",
            "cover_amount": "float",
            "annual_premium": "float"
          }
        ]
      }
    ]
  }
}
```

### Validation expectations

- `household`, `household.id`, `household.name`, and `members` are required.
- Every member must have `id`, `name`, `relation`, `age`, and `is_earning`.
- Monetary fields must be non-negative.
- Empty lists are valid for `bank_balances` and `life_insurance`.
- Missing required structural fields should raise a Pydantic validation error.
- `annual_income`, `monthly_expenses`, and `dependents` may default to zero when omitted, but the analyzer must never invent positive values.

---

## 2. Business Rules

### 2.1 Emergency Fund

Use the whole household, not just earners.

| Rule | Implementation |
|---|---|
| Monthly expenses scope | Sum `monthly_expenses` across all members |
| Liquid savings scope | Sum every `bank_balances[].balance` across all members |
| Account type handling | In this simplified assignment, do not filter by `account_type`; all bank balances count |
| Required amount | `6 * total_monthly_expenses` |
| Gap amount | `max(0, required_amount - total_liquid_savings)` |
| Months covered | `total_liquid_savings / total_monthly_expenses`, rounded to 1 decimal |

Severity thresholds:

- `adequate`: months covered >= 6
- `warning`: months covered >= 3 and < 6
- `critical`: months covered < 3

### 2.2 Life Cover

Analyze only members where `is_earning == True` and `annual_income > 0`.

| Rule | Implementation |
|---|---|
| Required cover | `10 * annual_income` |
| Existing cover | Sum all `life_insurance[].cover_amount` values for that member |
| Policy types | Term, endowment, ULIP, and whole-life policies all count toward existing cover |
| Gap amount | `max(0, required_cover - existing_cover)` |

Severity thresholds:

- `adequate`: `gap_amount == 0`
- `warning`: `0 < gap_amount <= annual_income * 5`
- `critical`: `existing_cover == 0` or `gap_amount > annual_income * 5`

### 2.3 Household Health Score

Start at 100 and deduct:

| Event | Deduction |
|---|---|
| Emergency fund critical | -25 |
| Emergency fund warning | -10 |
| Life cover critical (per member) | -20 |
| Life cover warning (per member) | -10 |
| Adequate status | 0 |

Clamp the final score to the `[0, 100]` range.

### 2.4 Recommendations

- Return up to 5 recommendations total.
- Prioritize in this order:
  1. Critical life cover gaps with zero existing cover
  2. Other critical life cover gaps
  3. Warning life cover gaps
  4. Emergency fund gap
- Each recommendation should be 1-2 sentences, plain language, and user-facing.
- Use Indian money wording such as `Rs. 96 lakh` or `Rs. 1.8 crore`.
- Do not recommend specific insurers, product SKUs, or tax strategies.
- A generic reference to a product type like "term insurance" is acceptable.

---

## 3. Output Schema

Return a single Pydantic model or dict matching this structure:

```json
{
  "household_id": "string",
  "household_name": "string",
  "analysis_date": "YYYY-MM-DD",
  "household_health_score": "integer 0-100",
  "emergency_fund": {
    "total_liquid_savings": "float",
    "total_monthly_expenses": "float",
    "required_amount": "float",
    "gap_amount": "float",
    "months_covered": "float",
    "severity": "adequate | warning | critical",
    "explanation": "string"
  },
  "life_cover": [
    {
      "member_id": "string",
      "member_name": "string",
      "annual_income": "float",
      "required_cover": "float",
      "existing_cover": "float",
      "gap_amount": "float",
      "severity": "adequate | warning | critical",
      "explanation": "string"
    }
  ],
  "skipped_members": [
    {
      "member_id": "string",
      "member_name": "string",
      "reason": "string"
    }
  ],
  "recommendations": ["string"],
  "metadata": {
    "total_members": "integer",
    "earning_members_analyzed": "integer",
    "members_skipped_from_life_cover": "integer",
    "non_earning_members_skipped": "integer",
    "zero_income_earners_skipped": "integer"
  }
}
```

Notes:

- `skipped_members` is the authoritative list of excluded members.
- `non_earning_members_skipped` counts only non-earners.
- `zero_income_earners_skipped` counts members flagged as earning but lacking usable income data.

---

## 4. Edge Cases

| Scenario | Expected behavior |
|---|---|
| Child or elderly parent is non-earning | Exclude from life cover analysis; include in `skipped_members`; still count their expenses and balances in emergency fund |
| Member has `is_earning = true` but `annual_income = 0` | Skip life cover analysis with an explicit reason |
| Member has no bank accounts | Treat as zero liquid savings contribution |
| Member has no life insurance | Existing cover is zero |
| Existing cover exceeds required cover | Gap becomes zero and severity is `adequate` |
| All members are non-earning | `life_cover` should be empty; score depends only on emergency fund |
| Single-member household | Apply the same rules normally |
| All monthly expenses are zero | Required emergency fund is zero; gap is zero; months covered is infinity; severity is `adequate` |
| Partial or malformed data | Raise validation error instead of guessing |

---

## 5. Implementation Constraints

- Language: Python 3.10+
- Models: Pydantic v2
- File layout:
  - `src/models.py`
  - `src/analyzer.py`
  - `src/tests.py`
- Main function signature:

```python
def analyze_household(household_data: dict) -> GapReport:
    ...
```

- The analyzer logic must stay pure and side-effect free.
- No HTTP calls, database code, Docker, or framework setup.
- A tiny `__main__` demo runner is optional, but keep it lightweight.
- If printing JSON in a CLI runner, make it UTF-8 safe on Windows.

---

## 6. Verification Targets

For the provided Sharma household, the implementation must produce:

- `total_liquid_savings = 681000`
- `total_monthly_expenses = 140000`
- `required_amount = 840000`
- `emergency_fund.gap_amount = 159000`
- `emergency_fund.months_covered = 4.9`
- `emergency_fund.severity = warning`
- Rajesh: existing cover `6000000`, required cover `18000000`, gap `12000000`, severity `critical`
- Priya: existing cover `0`, required cover `9600000`, gap `9600000`, severity `critical`
- `household_health_score = 50`
- `members_skipped_from_life_cover = 2`
- `non_earning_members_skipped = 2`
- `zero_income_earners_skipped = 0`

Also include tests for:

1. A no-gap household with score `100`
2. A genuine edge case such as an elderly non-earner
3. A member marked earning with zero income
4. Zero-expense handling
5. Partial-data validation
