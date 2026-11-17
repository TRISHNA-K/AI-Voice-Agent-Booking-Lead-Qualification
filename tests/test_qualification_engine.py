"""Unit tests for BANT Lead Qualification Engine."""

import pytest
from src.tools.qualification_engine import QualificationEngine, BANTParameters


def test_high_value_sql_lead():
    engine = QualificationEngine(min_qualified_score=70, min_warm_score=40)
    bant = BANTParameters(
        need_pain_point="Losing 30% of booking revenue due to unanswered calls",
        need_urgency="critical",
        authority_role="Chief Executive Officer",
        is_decision_maker=True,
        timeline_phrase="within 30 days",
        timeline_months=1,
        budget_range="$30k allocated budget",
        budget_approved=True,
    )

    result = engine.evaluate(bant)
    assert result.total_score >= 80
    assert result.stage == "Sales Qualified Lead (SQL)"
    assert result.recommended_action == "book_meeting"
    assert result.need_score == 25
    assert result.authority_score == 25
    assert result.timeline_score == 25
    assert result.budget_score == 25


def test_warm_mql_lead():
    engine = QualificationEngine(min_qualified_score=70, min_warm_score=40)
    bant = BANTParameters(
        need_pain_point="Evaluating voice AI options for next year",
        need_urgency="medium",
        authority_role="Marketing Specialist",
        is_decision_maker=False,
        timeline_phrase="in 6 months",
        timeline_months=6,
        budget_range="exploring",
        budget_approved=False,
    )

    result = engine.evaluate(bant)
    assert 40 <= result.total_score < 70
    assert result.stage == "Marketing Qualified Lead (MQL)"
    assert result.recommended_action == "nurture_followup"


def test_disqualified_lead():
    engine = QualificationEngine(min_qualified_score=70, min_warm_score=40)
    bant = BANTParameters(
        need_pain_point=None,
        need_urgency="none",
        authority_role="Intern",
        is_decision_maker=False,
        timeline_phrase="not planned",
        timeline_months=12,
        budget_range="zero / looking for free",
        budget_approved=False,
    )

    result = engine.evaluate(bant)
    assert result.total_score < 40
    assert result.stage == "Disqualified"
    assert result.recommended_action == "polite_close"
