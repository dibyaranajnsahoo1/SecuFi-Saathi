# SecuFi - Emergency Fund and Life Cover Gap Analyzer

AI-assisted household protection gap analyzer for Indian families. It calculates:

- emergency fund adequacy against a 6-month household-expense benchmark
- life cover adequacy for each earning member against a 10x income benchmark
- plain-language recommendations and an overall household health score

## Requirements

- Python 3.10+
- `pydantic` v2

## Install

```bash
pip install pydantic
```

## Run the tests

```bash
cd src
python tests.py
```

Expected result: `24/24 passed - ALL TESTS PASSED`

## Run the analyzer

```bash
cd src
python analyzer.py
```

You can also pass a JSON file:

```bash
cd src
python analyzer.py path/to/household.json
```

## Project structure

```text
SecuFi-s-gap-analyzer/
|-- CLAUDE.md
|-- README.md
|-- REFLECTION.md
|-- prompts/
|   |-- system_prompt.md
|   `-- skills/
|       `-- indian-insurance-basics/
|           `-- SKILL.md
`-- src/
    |-- analyzer.py
    |-- models.py
    `-- tests.py
```

## Design choices

- All household members' expenses count toward the emergency fund requirement.
- All members' bank balances count toward liquid savings in this simplified assignment.
- Only members with `is_earning=True` and `annual_income > 0` receive a life cover analysis.
- Non-earners and zero-income earners are listed in `skipped_members` with explicit reasons.
- The CLI runner configures UTF-8 output so it works cleanly in a normal Windows terminal.

## Sharma household verification targets

- Emergency fund savings: `681000`
- Emergency fund required amount: `840000`
- Emergency fund gap: `159000`
- Emergency fund months covered: `4.9`
- Rajesh life cover gap: `12000000`
- Priya life cover gap: `9600000`
- Household health score: `50`
