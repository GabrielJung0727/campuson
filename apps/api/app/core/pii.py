"""PII(개인정보) 마스킹 유틸 — v0.9.

학생 이메일/학번/연락처/이름 등을 로그/응답에서 가공하기 위한 공통 함수.
ADMIN/DEVELOPER 외에는 masked 버전을 반환하는 responder 헬퍼 포함.

사용 예
-------
```python
from app.core.pii import mask_email, mask_student_no, mask_user_payload

resp = mask_user_payload(user_dict, viewer_role=actor.role)
```
"""

from __future__ import annotations

import re
from typing import Any

from app.models.enums import Role

EMAIL_PATTERN = re.compile(r"^(?P<user>[^@]+)@(?P<domain>.+)$")
PHONE_PATTERN = re.compile(r"(\d{2,3})-?(\d{3,4})-?(\d{3,4})")


def mask_email(email: str | None) -> str | None:
    """이메일 앞부분 마스킹 — 예: g***@naver.com."""
    if not email:
        return email
    m = EMAIL_PATTERN.match(email)
    if not m:
        return "***"
    user, domain = m.group("user"), m.group("domain")
    if len(user) <= 1:
        masked_user = "*"
    else:
        masked_user = user[0] + "*" * max(1, len(user) - 1)
    return f"{masked_user}@{domain}"


def mask_phone(phone: str | None) -> str | None:
    """전화번호 중간 4자리 마스킹 — 010-****-5678."""
    if not phone:
        return phone
    m = PHONE_PATTERN.search(phone)
    if not m:
        return "***"
    return f"{m.group(1)}-****-{m.group(3)}"


def mask_name(name: str | None) -> str | None:
    """이름 마스킹 — 홍길동 → 홍*동, 김영 → 김*."""
    if not name:
        return name
    if len(name) == 1:
        return "*"
    if len(name) == 2:
        return name[0] + "*"
    # 3자 이상 — 가운데만 마스킹
    return name[0] + "*" * (len(name) - 2) + name[-1]


def mask_student_no(student_no: str | None) -> str | None:
    """학번 마스킹 — 2024123456 → 2024****56."""
    if not student_no:
        return student_no
    if len(student_no) < 6:
        return "*" * len(student_no)
    return student_no[:4] + "*" * (len(student_no) - 6) + student_no[-2:]


def mask_user_payload(
    payload: dict[str, Any], *, viewer_role: Role, viewer_is_self: bool = False,
) -> dict[str, Any]:
    """사용자 데이터 응답에서 PII 필드 자동 마스킹.

    ADMIN/DEVELOPER/본인: 원본 유지.
    PROFESSOR: 이메일/전화 마스킹, 이름/학번은 교육 목적상 유지.
    STUDENT: 본인 외에는 이름까지 마스킹.
    """
    # 원본 유지 케이스
    if viewer_is_self or viewer_role in (Role.ADMIN, Role.DEVELOPER):
        return payload

    masked = dict(payload)

    if viewer_role == Role.PROFESSOR:
        if "email" in masked:
            masked["email"] = mask_email(masked.get("email"))
        if "phone" in masked:
            masked["phone"] = mask_phone(masked.get("phone"))
        return masked

    # STUDENT가 다른 학생 보는 케이스 — 최대 마스킹
    if "email" in masked:
        masked["email"] = mask_email(masked.get("email"))
    if "phone" in masked:
        masked["phone"] = mask_phone(masked.get("phone"))
    if "name" in masked:
        masked["name"] = mask_name(masked.get("name"))
    if "student_no" in masked:
        masked["student_no"] = mask_student_no(masked.get("student_no"))
    return masked


def mask_free_text(text: str) -> str:
    """자유 텍스트에서 이메일/전화 패턴 자동 마스킹 — 로그/리포트용."""
    if not text:
        return text
    # 이메일
    text = re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        lambda m: mask_email(m.group()) or "***",
        text,
    )
    # 전화
    text = PHONE_PATTERN.sub(r"\1-****-\3", text)
    return text
