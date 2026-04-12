"""실습 평가 실시간 WebSocket 엔드포인트.

클라이언트 → 서버: MediaPipe 랜드마크 데이터 (JSON)
서버 → 클라이언트: 분석 결과 + 경고 + AI 피드백 (JSON)

프로토콜:
  → {"type": "pose", "session_id": "...", "landmarks": [...]}
  → {"type": "snapshot", "session_id": "...", "image_base64": "..."}  (optional, for YOLO)
  ← {"type": "analysis", "data": {...}}
  ← {"type": "feedback", "data": {...}}
  ← {"type": "checklist_update", "data": {...}}
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.realtime_analysis import (
    get_or_create_analyzer,
    parse_landmarks,
    remove_analyzer,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 연결된 클라이언트 관리 (session_id → [websockets])
_connections: dict[str, list[WebSocket]] = {}


@router.websocket("/ws/practicum/{session_id}")
async def practicum_realtime(websocket: WebSocket, session_id: str):
    """실시간 실습 분석 WebSocket."""
    await websocket.accept()

    # 세션 연결 등록
    if session_id not in _connections:
        _connections[session_id] = []
    _connections[session_id].append(websocket)

    analyzer = None
    frame_count = 0

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "init":
                # 세션 초기화: 체크리스트 항목 + 카테고리 전달
                checklist_items = msg.get("checklist_items", [])
                category = msg.get("category", "")
                analyzer = get_or_create_analyzer(session_id, checklist_items, category)
                await websocket.send_json({
                    "type": "ready",
                    "message": "실시간 분석이 시작되었습니다.",
                })

            elif msg_type == "pose" and analyzer:
                landmarks_raw = msg.get("landmarks", [])
                landmarks = parse_landmarks(landmarks_raw)

                if not landmarks:
                    continue

                # 프레임 분석
                result = analyzer.process_frame(landmarks)
                frame_count += 1

                # 매 프레임 분석 결과 전송
                await websocket.send_json({
                    "type": "analysis",
                    "frame": frame_count,
                    "data": result,
                })

                # 30프레임(~1초)마다 체크리스트 업데이트 브로드캐스트
                if frame_count % 30 == 0:
                    await _broadcast(session_id, {
                        "type": "checklist_update",
                        "data": analyzer.checklist_status,
                    })

                # 10초마다 LLM 피드백 생성
                if frame_count % 300 == 0:
                    feedback = await analyzer.generate_realtime_feedback()
                    if feedback:
                        await _broadcast(session_id, {
                            "type": "feedback",
                            "data": feedback,
                        })

            elif msg_type == "stop" and analyzer:
                # 세션 종료 → 최종 피드백
                feedback = await analyzer.generate_realtime_feedback()
                await websocket.send_json({
                    "type": "final",
                    "data": {
                        "total_frames": frame_count,
                        "checklist_status": analyzer.checklist_status,
                        "feedback": feedback,
                    },
                })
                remove_analyzer(session_id)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: session=%s", session_id)
    except Exception:
        logger.exception("WebSocket error: session=%s", session_id)
    finally:
        if session_id in _connections:
            _connections[session_id] = [
                ws for ws in _connections[session_id] if ws != websocket
            ]
            if not _connections[session_id]:
                del _connections[session_id]


async def _broadcast(session_id: str, message: dict):
    """세션에 연결된 모든 클라이언트에 메시지 전송."""
    for ws in _connections.get(session_id, []):
        try:
            await ws.send_json(message)
        except Exception:
            pass
