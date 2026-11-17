"""BANT Lead Qualification Scoring Engine.

Implements structured evaluation across Budget, Authority, Need, and Timeline
with automated routing into SQL, MQL, or Disqualified stages.
"""

from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field

from config.settings import get_settings


class BANTParameters(BaseModel):
    """Extracted BANT parameters from conversation."""

    need_pain_point: Optional[str] = Field(
        None, description="The customer's core challenge or workflow bottleneck."
    )
    need_urgency: str = Field(
        "medium", description="critical, high, medium, low, or none"
    )

    authority_role: Optional[str] = Field(
        None, description="Caller's job title or role (e.g., CEO, VP Operations, Manager)."
    )
    is_decision_maker: bool = Field(
        False, description="Whether caller has budget and signing authority."
    )
    decision_process: Optional[str] = Field(
        None, description="Sole decision maker, committee member, or researcher."
    )

    timeline_phrase: Optional[str] = Field(
        None, description="Desired implementation window (e.g. this month, Q1, next quarter)."
    )
    timeline_months: Optional[int] = Field(
        None, description="Estimated time horizon in months."
    )

    budget_range: Optional[str] = Field(
        None, description="Stated budget or spend capability."
    )
    budget_approved: bool = Field(
        False, description="Whether budget has already been allocated or approved."
    )


class QualificationResult(BaseModel):
    """Scoring result with breakdown and routing recommendation."""

    total_score: int
    stage: str  # 'Sales Qualified Lead (SQL)', 'Marketing Qualified Lead (MQL)', 'Disqualified'
    budget_score: int
    authority_score: int
    need_score: int
    timeline_score: int
    recommended_action: str  # 'book_meeting', 'nurture_followup', 'polite_close'
    qualification_notes: str


class QualificationEngine:
    """Evaluates conversation details and calculates standardized lead score."""

    def __init__(
        self,
        min_qualified_score: Optional[int] = None,
        min_warm_score: Optional[int] = None,
    ):
        settings = get_settings()
        self.min_qualified_score = min_qualified_score or settings.BANT_MIN_QUALIFIED_SCORE
        self.min_warm_score = min_warm_score or settings.BANT_MIN_WARM_SCORE

    def evaluate(self, bant: BANTParameters) -> QualificationResult:
        """Score each dimension and return structured qualification result."""
        # 1. Need Score (0 to 25)
        need_score = 0
        urgency = (bant.need_urgency or "").lower()
        if urgency in ("critical", "high"):
            need_score = 25
        elif urgency == "medium":
            need_score = 15
        elif urgency == "low":
            need_score = 8
        elif bant.need_pain_point:
            need_score = 12

        # 2. Authority Score (0 to 25)
        authority_score = 0
        if bant.is_decision_maker:
            authority_score = 25
        elif bant.decision_process and "committee" in bant.decision_process.lower():
            authority_score = 18
        elif bant.authority_role:
            role = bant.authority_role.lower()
            if any(t in role for t in ["ceo", "cto", "founder", "owner", "president", "vp", "director"]):
                authority_score = 22
            elif any(t in role for t in ["manager", "lead", "head"]):
                authority_score = 15
            else:
                authority_score = 8

        # 3. Timeline Score (0 to 25)
        timeline_score = 0
        if bant.timeline_months is not None:
            if bant.timeline_months <= 1:
                timeline_score = 25
            elif bant.timeline_months <= 3:
                timeline_score = 20
            elif bant.timeline_months <= 6:
                timeline_score = 12
            else:
                timeline_score = 5
        elif bant.timeline_phrase:
            phrase = bant.timeline_phrase.lower()
            if any(w in phrase for w in ["immediately", "asap", "this month", "right now", "urgently"]):
                timeline_score = 25
            elif any(w in phrase for w in ["next month", "this quarter", "q1", "q2", "soon"]):
                timeline_score = 20
            elif any(w in phrase for w in ["6 months", "half year", "end of year"]):
                timeline_score = 10
            else:
                timeline_score = 5

        # 4. Budget Score (0 to 25)
        budget_score = 0
        if bant.budget_approved:
            budget_score = 25
        elif bant.budget_range:
            b_text = bant.budget_range.lower()
            if any(w in b_text for w in ["50k", "100k", "enterprise", "unlimited", "allocated", "approved"]):
                budget_score = 25
            elif any(w in b_text for w in ["10k", "20k", "30k", "flexible", "funded"]):
                budget_score = 18
            elif any(w in b_text for w in ["low", "cheap", "free", "no budget", "tight"]):
                budget_score = 5
            else:
                budget_score = 12

        total_score = need_score + authority_score + timeline_score + budget_score

        # Determine Stage & Action
        if total_score >= self.min_qualified_score:
            stage = "Sales Qualified Lead (SQL)"
            action = "book_meeting"
            notes = (
                f"Highly qualified (Score: {total_score}/100). High urgency ({bant.need_pain_point}), "
                f"authorized decision maker ({bant.authority_role}), timeline within 90 days. "
                "Action: Immediate executive discovery booking."
            )
        elif total_score >= self.min_warm_score:
            stage = "Marketing Qualified Lead (MQL)"
            action = "nurture_followup"
            notes = (
                f"Warm prospect (Score: {total_score}/100). Valid interest detected, but timeline or "
                "budget is flexible. Action: Send product overview and schedule follow-up."
            )
        else:
            stage = "Disqualified"
            action = "polite_close"
            notes = (
                f"Disqualified (Score: {total_score}/100). Insufficient alignment on timeline, authority, or budget."
            )

        return QualificationResult(
            total_score=total_score,
            stage=stage,
            budget_score=budget_score,
            authority_score=authority_score,
            need_score=need_score,
            timeline_score=timeline_score,
            recommended_action=action,
            qualification_notes=notes,
        )
