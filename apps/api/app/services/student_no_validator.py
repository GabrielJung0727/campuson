"""학번 검증 로직.

경복대학교 학번 형식: YY + 학과코드 + 일련번호 (예: 2455025 → 7자리)

규칙
----
1. 7~10자리 숫자 (경복대는 7자리)
2. 첫 2자리는 입학년도(YY) — 현재 연도 기준 ±6년 범위
3. 학과별 추가 검증은 향후 학교 측 데이터 협의 후 확장 가능

학생(STUDENT) 역할만 학번이 필수이며, 교수/관리자/개발자는 학번을 갖지 않는다.
"""

import re
from datetime import datetime

from app.models.enums import Department, Role

STUDENT_NO_PATTERN = re.compile(r"^\d{7,10}$")
ENROLLMENT_YEAR_RANGE_BACK = 6
ENROLLMENT_YEAR_RANGE_FORWARD = 1


class StudentNoValidationError(ValueError):
    """학번 검증 실패."""

    pass


def validate_student_no(student_no: str, department: Department) -> None:
    """학번 형식 + 입학년도 범위 검증.

    Parameters
    ----------
    student_no : str
        검증할 학번 문자열.
    department : Department
        학생의 소속 학과 (향후 학과별 검증 확장 시 사용).

    Raises
    ------
    StudentNoValidationError
        형식 위반 또는 입학년도 범위를 벗어났을 때.
    """
    if not student_no:
        raise StudentNoValidationError("학번이 비어있습니다.")

    if not STUDENT_NO_PATTERN.match(student_no):
        raise StudentNoValidationError("학번은 7~10자리 숫자여야 합니다.")

    year_prefix = int(student_no[:2])
    current_year_yy = datetime.now().year % 100

    # 60~99는 1900년대, 0~59는 2000년대로 단순 매핑
    full_year = 2000 + year_prefix if year_prefix < 60 else 1900 + year_prefix
    current_full_year = datetime.now().year

    if not (
        current_full_year - ENROLLMENT_YEAR_RANGE_BACK
        <= full_year
        <= current_full_year + ENROLLMENT_YEAR_RANGE_FORWARD
    ):
        raise StudentNoValidationError(
            f"학번의 입학년도({full_year})가 허용 범위를 벗어났습니다. "
            f"({current_full_year - ENROLLMENT_YEAR_RANGE_BACK}~"
            f"{current_full_year + ENROLLMENT_YEAR_RANGE_FORWARD}년)"
        )

    # 학과별 추가 검증은 향후 확장 (현재는 placeholder)
    _ = department


def validate_student_no_for_role(
    student_no: str | None,
    role: Role,
    department: Department,
) -> None:
    """역할에 따라 학번 필수 여부를 검증한다.

    - STUDENT: 학번 필수 + 형식 검증
    - 그 외: 학번 NULL 권장 (값이 있으면 무시되지 않고 형식만 가볍게 검증)
    """
    if role == Role.STUDENT:
        if not student_no:
            raise StudentNoValidationError("학생은 학번이 필수입니다.")
        validate_student_no(student_no, department)
    else:
        if student_no is not None:
            raise StudentNoValidationError(
                f"{role.value} 역할은 학번을 가질 수 없습니다."
            )
