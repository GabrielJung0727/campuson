"""민감 행위 감사 서비스 (v0.9).

AuditLogMiddleware가 모든 요청을 로깅하는 것과 별도로,
관리자/교수의 고위험 작업과 시험 부정행위 의심 이벤트를 별도 태깅한다.

설계 원칙
--------
- request_body에 {"_sensitive": "category"} 플래그 부여 → 대시보드/알림 대상
- 별도 테이블 없이 기존 audit_logs 인덱스 재사용 (path + user_id 조합 쿼리)
- SECURITY 카테고리는 Sentry/알림 연동
"""

from __future__ import annotations

import logging
import uuid
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class SensitiveCategory(str, Enum):
    """민감 행위 분류."""
    USER_ROLE_CHANGE = "user_role_change"
    USER_DELETE = "user_delete"
    QUESTION_BULK_MODIFY = "question_bulk_modify"
    GRADE_MODIFY = "grade_modify"
    EXAM_TAMPER_SUSPECT = "exam_tamper_suspect"
    DATA_EXPORT = "data_export"
    PERMISSION_BYPASS_ATTEMPT = "permission_bypass_attempt"
    FEATURE_FLAG_CHANGE = "feature_flag_change"
    SCHOOL_CONFIG_CHANGE = "school_config_change"
    PII_ACCESS = "pii_access"  # 대량 PII 조회


async def record_sensitive_action(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    user_role: str | None,
    category: SensitiveCategory,
    path: str,
    method: str = "POST",
    context: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """민감 행위 감사 레코드 — audit_logs에 특별 태깅하여 저장."""
    body = {"_sensitive": category.value}
    if context:
        # 민감 필드 제외하고 컨텍스트만
        body.update({k: v for k, v in context.items() if k.lower() not in {"password", "token"}})

    log = AuditLog(
        user_id=user_id,
        user_role=user_role,
        ip_address=ip_address,
        method=method,
        path=path[:500],
        request_body=body,
        status_code=200,
        latency_ms=0,
    )
    db.add(log)
    try:
        await db.commit()
    except Exception:  # noqa: BLE001
        await db.rollback()
        logger.exception("Failed to record sensitive action: %s", category.value)

    # 치명적 카테고리 → 별도 warning 로그 (Sentry 연동)
    if category in {
        SensitiveCategory.EXAM_TAMPER_SUSPECT,
        SensitiveCategory.PERMISSION_BYPASS_ATTEMPT,
    }:
        logger.warning(
            "SENSITIVE_ACTION category=%s user=%s path=%s ctx=%s",
            category.value, user_id, path, context,
        )


# === 시험 부정행위 탐지 휴리스틱 ===


def detect_exam_tampering(submission_context: dict) -> list[str]:
    """시험 제출 컨텍스트에서 부정행위 의심 신호 검출.

    Parameters
    ----------
    submission_context : dict
        {
            "duration_seconds": int,
            "expected_duration": int,
            "tab_switches": int,
            "focus_losses": int,
            "ip_changes": int,
            "ua_changes": int,
            "answer_count": int,
            "correct_count": int,
        }

    Returns
    -------
    list[str]
        의심 신호 목록 (빈 리스트면 정상)
    """
    signals: list[str] = []

    duration = submission_context.get("duration_seconds", 0)
    expected = submission_context.get("expected_duration", 0)
    if duration and expected:
        if duration < expected * 0.2:
            signals.append("suspicious_fast_completion")
        if duration > expected * 2.0:
            signals.append("excessive_duration")

    if submission_context.get("tab_switches", 0) > 10:
        signals.append("excessive_tab_switching")

    if submission_context.get("focus_losses", 0) > 15:
        signals.append("excessive_focus_loss")

    if submission_context.get("ip_changes", 0) > 0:
        signals.append("ip_change_during_exam")

    if submission_context.get("ua_changes", 0) > 0:
        signals.append("user_agent_change_during_exam")

    # 정답률 비정상 (답 수 대비)
    answer_count = submission_context.get("answer_count", 0)
    correct_count = submission_context.get("correct_count", 0)
    if answer_count >= 10 and duration and duration < answer_count * 5:
        # 문항당 5초 이내 풀이 → 의심
        signals.append("abnormally_fast_per_question")
    if answer_count >= 20 and correct_count == answer_count:
        # 전문항 정답 + 초고속 → 복합 의심
        signals.append("perfect_score_short_time")

    return signals
