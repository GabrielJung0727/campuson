"""단위 테스트 — 서비스 레이어 (v0.9).

순수 함수 및 비즈니스 로직 검증 (DB 미접근).
"""

import pytest

from app.services.osce_service import detect_timing_issues


class TestDetectTimingIssues:
    """시간 초과/순서 오류 탐지 함수 테스트."""

    def test_no_issues(self):
        items = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
        steps = [
            {"item_id": "A", "action": "check", "timestamp_sec": 10},
            {"item_id": "B", "action": "check", "timestamp_sec": 20},
            {"item_id": "C", "action": "check", "timestamp_sec": 30},
        ]
        events = detect_timing_issues(items, steps, time_limit_sec=60)
        assert events == []

    def test_order_error(self):
        items = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
        steps = [
            {"item_id": "B", "action": "check", "timestamp_sec": 10},  # B first = wrong
            {"item_id": "A", "action": "check", "timestamp_sec": 20},
            {"item_id": "C", "action": "check", "timestamp_sec": 30},
        ]
        events = detect_timing_issues(items, steps, time_limit_sec=60)
        order_errors = [e for e in events if e["event_type"] == "order_error"]
        assert len(order_errors) >= 1
        assert order_errors[0]["event_data"]["expected_item"] == "A"
        assert order_errors[0]["event_data"]["actual_item"] == "B"

    def test_timeout(self):
        items = [{"id": "A"}]
        steps = [
            {"item_id": "A", "action": "check", "timestamp_sec": 120},
        ]
        events = detect_timing_issues(items, steps, time_limit_sec=60)
        timeouts = [e for e in events if e["event_type"] == "timeout"]
        assert len(timeouts) == 1
        assert timeouts[0]["severity"] == "critical"
        assert timeouts[0]["event_data"]["overtime_sec"] == 60

    def test_empty_steps(self):
        items = [{"id": "A"}]
        events = detect_timing_issues(items, [], time_limit_sec=60)
        assert events == []


class TestErrorCodes:
    """에러 코드 상수 테스트."""

    def test_error_codes_defined(self):
        from app.core.error_handlers import ErrorCode
        assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
        assert ErrorCode.NOT_FOUND == "NOT_FOUND"
        assert ErrorCode.UNAUTHORIZED == "UNAUTHORIZED"
        assert ErrorCode.FORBIDDEN == "FORBIDDEN"
        assert ErrorCode.RATE_LIMITED == "RATE_LIMITED"


class TestCalendarEventDict:
    """캘린더 이벤트 dict 변환 테스트."""

    def test_event_to_dict_minimal(self):
        from unittest.mock import MagicMock
        from app.services.calendar_service import _event_to_dict

        event = MagicMock()
        event.id = "test-id"
        event.title = "Test Event"
        event.description = None
        event.event_type = "custom"
        event.start_at.isoformat.return_value = "2026-04-16T10:00:00"
        event.end_at = None
        event.all_day = False
        event.reference_type = None
        event.reference_id = None
        event.color = None
        event.reminder_minutes = None
        event.is_completed = False

        result = _event_to_dict(event)
        assert result["id"] == "test-id"
        assert result["title"] == "Test Event"
        assert result["end_at"] is None
        assert result["is_completed"] is False
