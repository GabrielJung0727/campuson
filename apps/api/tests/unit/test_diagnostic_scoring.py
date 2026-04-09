"""진단 테스트 채점 로직 단위 테스트."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import Level
from app.services.diagnostic_service import (
    _compute_section_scores,
    _determine_level,
    _extract_weak_areas,
)


@dataclass
class _Q:
    subject: str
    unit: str | None


def _mk_answers() -> list[tuple[_Q, bool]]:
    return [
        (_Q("성인간호학", "심혈관계"), True),
        (_Q("성인간호학", "심혈관계"), True),
        (_Q("성인간호학", "호흡기계"), False),
        (_Q("성인간호학", "호흡기계"), False),
        (_Q("기본간호학", "활력징후"), False),
        (_Q("기본간호학", "활력징후"), False),
        (_Q("기본간호학", "활력징후"), True),
        (_Q("모성간호학", "임신"), True),
        (_Q("모성간호학", "임신"), True),
        (_Q("모성간호학", "분만"), True),
    ]


class TestSectionScores:
    def test_per_subject(self) -> None:
        ss = _compute_section_scores(_mk_answers())
        assert ss["성인간호학"] == 0.5
        assert ss["기본간호학"] == 0.3333
        assert ss["모성간호학"] == 1.0


class TestWeakAreas:
    def test_threshold_60(self) -> None:
        wa = _extract_weak_areas(_mk_answers())
        # 호흡기계(0%), 활력징후(33%) 모두 < 60% → weak
        subjects = {(w["subject"], w["unit"]) for w in wa}
        assert ("성인간호학", "호흡기계") in subjects
        assert ("기본간호학", "활력징후") in subjects

    def test_priority_order(self) -> None:
        wa = _extract_weak_areas(_mk_answers())
        # 정답률 낮은 호흡기계가 priority 1
        assert wa[0]["subject"] == "성인간호학"
        assert wa[0]["unit"] == "호흡기계"
        assert wa[0]["priority"] == 1


class TestLevel:
    def test_advanced(self) -> None:
        assert _determine_level(0.85) == Level.ADVANCED
        assert _determine_level(0.80) == Level.ADVANCED

    def test_intermediate(self) -> None:
        assert _determine_level(0.50) == Level.INTERMEDIATE
        assert _determine_level(0.79) == Level.INTERMEDIATE

    def test_beginner(self) -> None:
        assert _determine_level(0.49) == Level.BEGINNER
        assert _determine_level(0.0) == Level.BEGINNER
