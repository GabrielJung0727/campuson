"""실시간 실습 분석 서비스.

MediaPipe 포즈 데이터 + YOLO 객체 탐지 + 규칙 기반 분석 + LLM 피드백.

아키텍처:
- 프론트엔드: MediaPipe Tasks Vision (브라우저, 30FPS)
  → 33개 랜드마크 좌표 + visibility 전송
- 백엔드 (이 모듈):
  1. 관절 각도 계산 (규칙 기반)
  2. 자세 안정성 분석
  3. 체크리스트 항목 자동 판정
  4. LLM 피드백 생성
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# MediaPipe Pose Landmark indices
# https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker
LANDMARK_NAMES = {
    0: "nose", 11: "left_shoulder", 12: "right_shoulder",
    13: "left_elbow", 14: "right_elbow",
    15: "left_wrist", 16: "right_wrist",
    23: "left_hip", 24: "right_hip",
    25: "left_knee", 26: "right_knee",
    27: "left_ankle", 28: "right_ankle",
}


@dataclass
class Landmark:
    x: float
    y: float
    z: float
    visibility: float = 0.0


@dataclass
class PoseAnalysis:
    """단일 프레임 분석 결과."""
    timestamp: float = 0.0
    # 주요 관절 각도
    left_elbow_angle: float = 0.0
    right_elbow_angle: float = 0.0
    left_shoulder_angle: float = 0.0
    right_shoulder_angle: float = 0.0
    left_knee_angle: float = 0.0
    right_knee_angle: float = 0.0
    # 자세 지표
    spine_angle: float = 0.0       # 척추 각도 (직립=180)
    head_tilt: float = 0.0         # 머리 기울기
    shoulder_level: float = 0.0    # 어깨 수평도
    hand_distance: float = 0.0     # 양손 거리
    hand_height: str = ""          # 손 높이 위치 (above_shoulder, chest, waist, below_waist)
    # 판정
    warnings: list[str] = field(default_factory=list)
    posture_score: float = 0.0     # 0~100


def calc_angle(a: Landmark, b: Landmark, c: Landmark) -> float:
    """세 점으로 관절 각도 계산 (도 단위)."""
    ba = (a.x - b.x, a.y - b.y, a.z - b.z)
    bc = (c.x - b.x, c.y - b.y, c.z - b.z)
    dot = sum(x * y for x, y in zip(ba, bc))
    mag_ba = math.sqrt(sum(x ** 2 for x in ba))
    mag_bc = math.sqrt(sum(x ** 2 for x in bc))
    if mag_ba * mag_bc == 0:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cos_angle))


def parse_landmarks(data: list[dict]) -> dict[int, Landmark]:
    """프론트엔드에서 받은 랜드마크 JSON → dict."""
    result = {}
    for item in data:
        idx = item.get("index", item.get("idx", -1))
        if idx >= 0:
            result[idx] = Landmark(
                x=item.get("x", 0), y=item.get("y", 0),
                z=item.get("z", 0), visibility=item.get("visibility", 0),
            )
    return result


def analyze_pose(landmarks: dict[int, Landmark]) -> PoseAnalysis:
    """단일 프레임의 포즈 분석."""
    analysis = PoseAnalysis(timestamp=time.time())
    warnings = []
    score = 100.0

    def get(idx: int) -> Landmark | None:
        lm = landmarks.get(idx)
        if lm and lm.visibility > 0.5:
            return lm
        return None

    ls, rs = get(11), get(12)  # shoulders
    le, re = get(13), get(14)  # elbows
    lw, rw = get(15), get(16)  # wrists
    lh, rh = get(23), get(24)  # hips
    lk, rk = get(25), get(26)  # knees
    nose = get(0)

    # 팔꿈치 각도
    if ls and le and lw:
        analysis.left_elbow_angle = calc_angle(ls, le, lw)
    if rs and re and rw:
        analysis.right_elbow_angle = calc_angle(rs, re, rw)

    # 어깨 각도 (팔 들어올린 정도)
    if lh and ls and le:
        analysis.left_shoulder_angle = calc_angle(lh, ls, le)
    if rh and rs and re:
        analysis.right_shoulder_angle = calc_angle(rh, rs, re)

    # 무릎 각도
    if lh and lk and get(27):
        analysis.left_knee_angle = calc_angle(lh, lk, get(27))
    if rh and rk and get(28):
        analysis.right_knee_angle = calc_angle(rh, rk, get(28))

    # 척추 각도 (어깨 중점 → 엉덩이 중점 → 수직)
    if ls and rs and lh and rh:
        mid_shoulder = Landmark(
            x=(ls.x + rs.x) / 2, y=(ls.y + rs.y) / 2, z=(ls.z + rs.z) / 2,
        )
        mid_hip = Landmark(
            x=(lh.x + rh.x) / 2, y=(lh.y + rh.y) / 2, z=(lh.z + rh.z) / 2,
        )
        # 수직 기준점 (엉덩이 바로 위)
        vertical_ref = Landmark(x=mid_hip.x, y=mid_hip.y - 1, z=mid_hip.z)
        analysis.spine_angle = calc_angle(mid_shoulder, mid_hip, vertical_ref)

        if analysis.spine_angle < 160:
            warnings.append(f"허리가 과도하게 굽어 있습니다 (척추 각도: {analysis.spine_angle:.0f}°, 권장: 170°+)")
            score -= min(20, (160 - analysis.spine_angle) * 1.5)

    # 어깨 수평도
    if ls and rs:
        analysis.shoulder_level = abs(ls.y - rs.y)
        if analysis.shoulder_level > 0.05:
            warnings.append("어깨가 한쪽으로 기울어져 있습니다.")
            score -= 5

    # 머리 기울기
    if nose and ls and rs:
        mid_shoulder_x = (ls.x + rs.x) / 2
        analysis.head_tilt = abs(nose.x - mid_shoulder_x)
        if analysis.head_tilt > 0.1:
            warnings.append(f"머리가 한쪽으로 치우쳐 있습니다. (목 부담 주의)")
            score -= 5

    # 손 높이 판정
    if lw and rw and ls and lh:
        avg_hand_y = (lw.y + rw.y) / 2
        if avg_hand_y < ls.y:
            analysis.hand_height = "above_shoulder"
        elif avg_hand_y < (ls.y + lh.y) / 2:
            analysis.hand_height = "chest"
        elif avg_hand_y < lh.y:
            analysis.hand_height = "waist"
        else:
            analysis.hand_height = "below_waist"

    # 양손 거리
    if lw and rw:
        analysis.hand_distance = math.sqrt(
            (lw.x - rw.x) ** 2 + (lw.y - rw.y) ** 2 + (lw.z - rw.z) ** 2
        )

    analysis.warnings = warnings
    analysis.posture_score = max(0, min(100, score))
    return analysis


class RealtimeSessionAnalyzer:
    """실시간 세션 분석 상태 관리.

    여러 프레임을 누적하여 동작 흐름과 절차 분석.
    """

    def __init__(self, checklist_items: list[dict], category: str):
        self.checklist_items = checklist_items
        self.category = category
        self.frame_analyses: list[PoseAnalysis] = []
        self.detected_actions: list[str] = []
        self.last_feedback_time: float = 0
        self.accumulated_warnings: dict[str, int] = {}
        self.checklist_status: dict[str, str] = {}  # item_id → status

    def process_frame(self, landmarks: dict[int, Landmark]) -> dict:
        """프레임 분석 + 누적 결과 반환."""
        analysis = analyze_pose(landmarks)
        self.frame_analyses.append(analysis)

        # 최근 30프레임만 유지
        if len(self.frame_analyses) > 30:
            self.frame_analyses = self.frame_analyses[-30:]

        # 경고 누적
        for w in analysis.warnings:
            key = w[:30]  # 경고 메시지 앞부분으로 그룹화
            self.accumulated_warnings[key] = self.accumulated_warnings.get(key, 0) + 1

        # 자세 기반 체크리스트 판정 (규칙 기반)
        self._evaluate_checklist(analysis)

        return {
            "posture_score": round(analysis.posture_score, 1),
            "spine_angle": round(analysis.spine_angle, 1),
            "left_elbow": round(analysis.left_elbow_angle, 1),
            "right_elbow": round(analysis.right_elbow_angle, 1),
            "hand_height": analysis.hand_height,
            "hand_distance": round(analysis.hand_distance, 3),
            "warnings": analysis.warnings,
            "checklist_status": self.checklist_status,
        }

    def _evaluate_checklist(self, analysis: PoseAnalysis):
        """규칙 기반 체크리스트 자동 판정."""
        # 공통: 자세 안정성
        for item in self.checklist_items:
            item_id = item["id"]
            label = item.get("label", "").lower()

            # 이미 success로 판정된 항목은 유지
            if self.checklist_status.get(item_id) == "success":
                continue

            # 자세 관련 키워드 매칭
            if "자세" in label or "체위" in label or "포지셔닝" in label:
                if analysis.posture_score >= 80:
                    self.checklist_status[item_id] = "success"
                elif analysis.posture_score >= 50:
                    self.checklist_status[item_id] = "partial"

            elif "손위생" in label or "손 씻" in label:
                # 손이 가슴 높이 + 양손 가까이 → 손위생 동작 감지
                if analysis.hand_height == "chest" and analysis.hand_distance < 0.15:
                    self.checklist_status[item_id] = "success"

            elif "장갑" in label or "보호구" in label:
                # 손이 서로 가까이 + 허리 높이 → 장갑 착용 동작
                if analysis.hand_height == "waist" and analysis.hand_distance < 0.2:
                    self.checklist_status[item_id] = "partial"

            elif "각도" in label or "ROM" in label.upper():
                # 팔꿈치 각도 변화 감지
                if analysis.left_elbow_angle > 30 or analysis.right_elbow_angle > 30:
                    self.checklist_status[item_id] = "partial"

    async def generate_realtime_feedback(self) -> dict:
        """LLM으로 현재까지의 분석 데이터 기반 실시간 피드백."""
        now = time.time()
        if now - self.last_feedback_time < 10:
            return {}  # 10초 간격 제한
        self.last_feedback_time = now

        if not self.frame_analyses:
            return {}

        recent = self.frame_analyses[-10:]
        avg_score = sum(a.posture_score for a in recent) / len(recent)

        # 반복 경고 상위 3개
        top_warnings = sorted(
            self.accumulated_warnings.items(), key=lambda x: x[1], reverse=True,
        )[:3]

        from app.core.llm import get_llm_gateway

        system_prompt = (
            "당신은 한국 보건의료 실습 교육 AI 코치입니다. "
            "학생의 실시간 자세 분석 데이터를 보고 짧은 코칭 피드백을 제공합니다. "
            "한국어로, 격려와 함께 구체적 개선점을 2~3문장으로 간결하게 전달하세요. "
            "JSON으로 응답: {\"feedback\": \"...\", \"alert\": \"...\"|null}"
        )

        checklist_progress = sum(
            1 for s in self.checklist_status.values() if s == "success"
        )
        total = len(self.checklist_items)

        user_prompt = (
            f"실습 유형: {self.category}\n"
            f"평균 자세 점수: {avg_score:.0f}/100\n"
            f"체크리스트 진행: {checklist_progress}/{total}\n"
            f"반복 경고: {', '.join(w for w, _ in top_warnings) if top_warnings else '없음'}\n"
            f"현재 손 위치: {recent[-1].hand_height}\n"
            f"척추 각도: {recent[-1].spine_angle:.0f}°"
        )

        try:
            gateway = get_llm_gateway()
            result = await gateway.generate(system=system_prompt, user=user_prompt)
            match = re.search(r"\{[\s\S]*\}", result.content)
            if match:
                return json.loads(match.group())
        except Exception:
            logger.exception("Realtime feedback LLM failed")

        # Fallback
        if avg_score < 60:
            return {"feedback": "자세를 바로 잡아주세요. 허리를 펴고 어깨를 수평으로 유지하세요.", "alert": "자세 교정 필요"}
        return {"feedback": "자세가 양호합니다. 체크리스트 항목을 순서대로 수행하세요.", "alert": None}


# 세션 관리 (메모리 기반)
_active_analyzers: dict[str, RealtimeSessionAnalyzer] = {}


def get_or_create_analyzer(session_id: str, checklist_items: list[dict], category: str) -> RealtimeSessionAnalyzer:
    if session_id not in _active_analyzers:
        _active_analyzers[session_id] = RealtimeSessionAnalyzer(checklist_items, category)
    return _active_analyzers[session_id]


def remove_analyzer(session_id: str):
    _active_analyzers.pop(session_id, None)
