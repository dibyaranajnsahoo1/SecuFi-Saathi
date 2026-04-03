"""
SecuFi Gap Analyzer - data models.

All input and output Pydantic v2 models for the Emergency Fund and
Life Cover Gap Analyzer.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    """Severity tiers used across the report."""

    ADEQUATE = "adequate"
    WARNING = "warning"
    CRITICAL = "critical"


class BankBalance(BaseModel):
    """A single bank account balance entry."""

    bank: str = Field(min_length=1)
    account_type: str = Field(min_length=1, description="For example: savings or current")
    balance: float = Field(ge=0, description="Account balance in INR")


class LifeInsurancePolicy(BaseModel):
    """A single life insurance policy held by one member."""

    provider: str = Field(min_length=1)
    type: str = Field(min_length=1, description="For example: term, endowment, ULIP")
    cover_amount: float = Field(ge=0, description="Sum assured in INR")
    annual_premium: float = Field(ge=0, description="Annual premium in INR")


class HouseholdMember(BaseModel):
    """One household member from the enriched input payload."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    age: int = Field(ge=0, le=120)
    is_earning: bool
    annual_income: float = Field(ge=0, default=0.0)
    monthly_expenses: float = Field(ge=0, default=0.0)
    dependents: int = Field(ge=0, default=0)
    bank_balances: list[BankBalance] = Field(default_factory=list)
    life_insurance: list[LifeInsurancePolicy] = Field(default_factory=list)


class Household(BaseModel):
    """Household wrapper for all members."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    members: list[HouseholdMember] = Field(min_length=1)


class HouseholdInput(BaseModel):
    """Top-level input wrapper."""

    household: Household


class EmergencyFundAnalysis(BaseModel):
    """Result of the emergency fund gap analysis."""

    total_liquid_savings: float
    total_monthly_expenses: float
    required_amount: float
    gap_amount: float
    months_covered: float
    severity: SeverityLevel
    explanation: str


class LifeCoverAnalysis(BaseModel):
    """Result of the life cover gap analysis for one earning member."""

    member_id: str
    member_name: str
    annual_income: float
    required_cover: float
    existing_cover: float
    gap_amount: float
    severity: SeverityLevel
    explanation: str


class SkippedMember(BaseModel):
    """A member excluded from life cover analysis, with reason."""

    member_id: str
    member_name: str
    reason: str


class AnalysisMetadata(BaseModel):
    """Summary counts for the analysis run."""

    total_members: int = Field(ge=0)
    earning_members_analyzed: int = Field(ge=0)
    members_skipped_from_life_cover: int = Field(ge=0)
    non_earning_members_skipped: int = Field(ge=0)
    zero_income_earners_skipped: int = Field(ge=0)


class GapReport(BaseModel):
    """The complete household gap report returned by analyze_household()."""

    household_id: str
    household_name: str
    analysis_date: str
    household_health_score: int = Field(ge=0, le=100)
    emergency_fund: EmergencyFundAnalysis
    life_cover: list[LifeCoverAnalysis]
    skipped_members: list[SkippedMember]
    recommendations: list[str]
    metadata: AnalysisMetadata
