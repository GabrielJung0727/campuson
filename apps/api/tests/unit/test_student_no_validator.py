"""학번 검증 단위 테스트."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.models.enums import Department, Role
from app.services.student_no_validator import (
    StudentNoValidationError,
    validate_student_no,
    validate_student_no_for_role,
)


class TestStudentNoFormat:
    def test_valid_8_digit(self) -> None:
        # 현재 연도 - 2 학번
        yy = (datetime.now().year - 2) % 100
        validate_student_no(f"{yy:02d}001234", Department.NURSING)

    def test_too_short(self) -> None:
        with pytest.raises(StudentNoValidationError, match="8~10자리"):
            validate_student_no("1234567", Department.NURSING)

    def test_non_numeric(self) -> None:
        with pytest.raises(StudentNoValidationError, match="8~10자리"):
            validate_student_no("24abc123", Department.NURSING)

    def test_year_too_old(self) -> None:
        with pytest.raises(StudentNoValidationError, match="입학년도"):
            validate_student_no("90001234", Department.NURSING)


class TestRolePolicy:
    def test_student_requires_no(self) -> None:
        with pytest.raises(StudentNoValidationError, match="학생은"):
            validate_student_no_for_role(None, Role.STUDENT, Department.NURSING)

    def test_professor_must_have_none(self) -> None:
        with pytest.raises(StudentNoValidationError, match="가질 수 없"):
            validate_student_no_for_role(
                "24001234", Role.PROFESSOR, Department.NURSING
            )

    def test_admin_must_have_none(self) -> None:
        # Admin도 학번을 가질 수 없음
        with pytest.raises(StudentNoValidationError):
            validate_student_no_for_role(
                "24001234", Role.ADMIN, Department.NURSING
            )

    def test_student_valid(self) -> None:
        yy = (datetime.now().year - 1) % 100
        validate_student_no_for_role(
            f"{yy:02d}001234", Role.STUDENT, Department.NURSING
        )
