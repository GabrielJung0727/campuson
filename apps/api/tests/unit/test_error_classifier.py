"""오답 분류 룰 단위 테스트."""

from __future__ import annotations

import pytest

from app.models.enums import ErrorType
from app.services.learning_history_service import classify_error


class TestErrorClassifier:
    def test_correct_returns_none(self) -> None:
        assert (
            classify_error(is_correct=True, solving_time_sec=30, prior_wrong_count=0)
            is None
        )

    def test_careless_short_time(self) -> None:
        assert (
            classify_error(is_correct=False, solving_time_sec=5, prior_wrong_count=0)
            == ErrorType.CARELESS
        )

    def test_application_gap_long_time(self) -> None:
        assert (
            classify_error(is_correct=False, solving_time_sec=200, prior_wrong_count=0)
            == ErrorType.APPLICATION_GAP
        )

    def test_concept_gap_repeated(self) -> None:
        assert (
            classify_error(is_correct=False, solving_time_sec=50, prior_wrong_count=2)
            == ErrorType.CONCEPT_GAP
        )

    def test_confusion_default(self) -> None:
        assert (
            classify_error(is_correct=False, solving_time_sec=50, prior_wrong_count=0)
            == ErrorType.CONFUSION
        )

    @pytest.mark.parametrize(
        "time_sec,prior,expected",
        [
            (9, 0, ErrorType.CARELESS),
            (180, 0, ErrorType.APPLICATION_GAP),
            (179, 0, ErrorType.CONFUSION),
            (50, 1, ErrorType.CONCEPT_GAP),  # 1 + 1 == 2 → CONCEPT_GAP
        ],
    )
    def test_boundary_values(self, time_sec, prior, expected) -> None:
        assert (
            classify_error(
                is_correct=False, solving_time_sec=time_sec, prior_wrong_count=prior
            )
            == expected
        )
