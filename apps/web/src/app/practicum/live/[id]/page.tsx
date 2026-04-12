'use client';

import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

interface ChecklistItem { id: string; label: string; points: number; is_critical: boolean }
interface SessionData {
  id: string; mode: string; status: string; scenario_name: string; scenario_category_label: string;
  checklist_items: ChecklistItem[]; total_points: number;
}
interface AnalysisData {
  posture_score: number; spine_angle: number;
  left_elbow: number; right_elbow: number;
  hand_height: string; hand_distance: number;
  warnings: string[]; checklist_status: Record<string, string>;
}
interface FeedbackData { feedback: string; alert: string | null }

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/api/v1';

const HAND_HEIGHT_LABEL: Record<string, string> = {
  above_shoulder: '어깨 위', chest: '가슴', waist: '허리', below_waist: '허리 아래',
};

const STATUS_COLOR: Record<string, string> = {
  success: 'bg-emerald-500', partial: 'bg-amber-500', fail: 'bg-red-500', danger: 'bg-rose-700',
};

export default function PracticumLivePage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { id: sessionId } = useParams<{ id: string }>();

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const animFrameRef = useRef<number>(0);

  const [session, setSession] = useState<SessionData | null>(null);
  const [connected, setConnected] = useState(false);
  const [recording, setRecording] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [feedbacks, setFeedbacks] = useState<FeedbackData[]>([]);
  const [checklistStatus, setChecklistStatus] = useState<Record<string, string>>({});
  const [frameCount, setFrameCount] = useState(0);
  const [cameraError, setCameraError] = useState('');

  useEffect(() => {
    if (!loading && !user) router.push('/login');
  }, [user, loading, router]);

  // Fetch session data
  useEffect(() => {
    if (user && sessionId) {
      api.getPracticumSession(sessionId).then((d: unknown) => setSession(d as SessionData)).catch(() => {});
    }
  }, [user, sessionId]);

  // Start camera
  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setCameraError('');
    } catch {
      setCameraError('카메라 접근이 거부되었습니다. 브라우저 권한을 확인하세요.');
    }
  }, []);

  useEffect(() => {
    startCamera();
    return () => {
      if (videoRef.current?.srcObject) {
        (videoRef.current.srcObject as MediaStream).getTracks().forEach((t) => t.stop());
      }
    };
  }, [startCamera]);

  // WebSocket connection
  const connectWS = useCallback(() => {
    if (!session) return;
    const ws = new WebSocket(`${WS_BASE}/ws/practicum/${sessionId}`);

    ws.onopen = () => {
      setConnected(true);
      // Init message
      ws.send(JSON.stringify({
        type: 'init',
        checklist_items: session.checklist_items,
        category: session.scenario_category_label,
      }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'analysis') {
        setAnalysis(msg.data);
        setFrameCount(msg.frame);
        if (msg.data.checklist_status) {
          setChecklistStatus(msg.data.checklist_status);
        }
      } else if (msg.type === 'feedback') {
        setFeedbacks((prev) => [msg.data, ...prev].slice(0, 5));
      } else if (msg.type === 'checklist_update') {
        setChecklistStatus(msg.data);
      }
    };

    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    wsRef.current = ws;
  }, [session, sessionId]);

  // MediaPipe pose detection loop (using browser MediaPipe)
  const startAnalysis = useCallback(async () => {
    if (!videoRef.current || !wsRef.current) return;
    setRecording(true);

    // Dynamic import of MediaPipe
    const vision = await import('@mediapipe/tasks-vision');
    const { PoseLandmarker, FilesetResolver } = vision;

    const filesetResolver = await FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
    );

    const poseLandmarker = await PoseLandmarker.createFromOptions(filesetResolver, {
      baseOptions: {
        modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
        delegate: 'GPU',
      },
      runningMode: 'VIDEO',
      numPoses: 1,
    });

    let lastTimestamp = -1;

    const detectLoop = () => {
      if (!videoRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        animFrameRef.current = requestAnimationFrame(detectLoop);
        return;
      }

      const video = videoRef.current;
      const now = performance.now();

      if (video.currentTime !== lastTimestamp && video.readyState >= 2) {
        lastTimestamp = video.currentTime;

        const result = poseLandmarker.detectForVideo(video, now);

        if (result.landmarks && result.landmarks.length > 0) {
          const landmarks = result.landmarks[0].map((lm: { x: number; y: number; z: number; visibility?: number }, idx: number) => ({
            index: idx,
            x: lm.x,
            y: lm.y,
            z: lm.z,
            visibility: lm.visibility ?? 1.0,
          }));

          // Draw skeleton on canvas
          drawPose(landmarks);

          // Send to server (throttle: every 3rd frame)
          if (frameCount % 3 === 0) {
            wsRef.current.send(JSON.stringify({
              type: 'pose',
              session_id: sessionId,
              landmarks,
            }));
          }
        }
      }

      animFrameRef.current = requestAnimationFrame(detectLoop);
    };

    detectLoop();
  }, [sessionId, frameCount]);

  function drawPose(landmarks: Array<{ index: number; x: number; y: number; visibility: number }>) {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Connection lines
    const connections = [
      [11, 13], [13, 15], [12, 14], [14, 16], // arms
      [11, 12], [23, 24], // torso
      [11, 23], [12, 24], // sides
      [23, 25], [25, 27], [24, 26], [26, 28], // legs
    ];

    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 3;
    for (const [a, b] of connections) {
      const la = landmarks.find((l) => l.index === a);
      const lb = landmarks.find((l) => l.index === b);
      if (la && lb && la.visibility > 0.5 && lb.visibility > 0.5) {
        ctx.beginPath();
        ctx.moveTo(la.x * canvas.width, la.y * canvas.height);
        ctx.lineTo(lb.x * canvas.width, lb.y * canvas.height);
        ctx.stroke();
      }
    }

    // Joint points
    for (const lm of landmarks) {
      if (lm.visibility < 0.5) continue;
      ctx.beginPath();
      ctx.arc(lm.x * canvas.width, lm.y * canvas.height, 5, 0, 2 * Math.PI);
      ctx.fillStyle = lm.index <= 10 ? '#f87171' : '#34d399';
      ctx.fill();
    }
  }

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleStop() {
    cancelAnimationFrame(animFrameRef.current);
    setRecording(false);
    setSaving(true);

    // 1. WebSocket stop → 최종 피드백 받기
    let finalFeedback: FeedbackData | null = null;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop', session_id: sessionId }));
      // 잠시 대기
      await new Promise((r) => setTimeout(r, 500));
      wsRef.current.close();
    }

    // 2. 체크리스트 결과 → DB 저장 (PATCH /practicum/sessions/{id})
    try {
      const items = session!.checklist_items;
      const results = items.map((item) => {
        const status = checklistStatus[item.id] || 'fail';
        const pts = status === 'success' ? item.points : status === 'partial' ? Math.round(item.points * 0.5) : 0;
        return { item_id: item.id, status, points_earned: pts };
      });

      await api.submitPracticumSession(sessionId, { checklist_results: results });

      // 3. AI 피드백 생성 + 저장
      await api.generatePracticumFeedback(sessionId);

      setSaved(true);
    } catch (err) {
      alert(`저장 실패: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSaving(false);
    }
  }

  if (loading || !user || !session) return <div className="p-8 text-center">로딩 중...</div>;

  const totalChecked = Object.values(checklistStatus).filter((s) => s === 'success').length;
  const totalItems = session.checklist_items.length;
  const scoreColor = (analysis?.posture_score ?? 0) >= 80 ? 'text-emerald-400' : (analysis?.posture_score ?? 0) >= 50 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Top bar */}
      <header className="border-b border-slate-800 bg-slate-950/95 px-4 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-teal-500/20 px-3 py-1 text-xs font-bold text-teal-400">LIVE</span>
            <span className="font-semibold">{session.scenario_name}</span>
            <span className="text-xs text-slate-500">{session.scenario_category_label}</span>
          </div>
          <div className="flex items-center gap-3">
            {connected && <span className="flex items-center gap-1 text-xs text-emerald-400"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />연결됨</span>}
            <span className="text-xs text-slate-500">Frame #{frameCount}</span>
            <Link href="/practicum" className="text-sm text-slate-400 hover:text-white">&larr; 목록</Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-4">
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          {/* Left: Camera + Overlay */}
          <div>
            <div className="relative rounded-2xl overflow-hidden bg-black aspect-[4/3]">
              {cameraError ? (
                <div className="flex h-full items-center justify-center text-red-400 text-sm">{cameraError}</div>
              ) : (
                <>
                  <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
                  <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />

                  {/* Overlay: posture score */}
                  {analysis && (
                    <div className="absolute top-4 left-4 rounded-xl bg-black/60 backdrop-blur-sm px-4 py-3">
                      <div className="text-xs text-slate-400">자세 점수</div>
                      <div className={`text-3xl font-black ${scoreColor}`}>
                        {analysis.posture_score.toFixed(0)}
                      </div>
                    </div>
                  )}

                  {/* Overlay: warnings */}
                  {analysis && analysis.warnings.length > 0 && (
                    <div className="absolute bottom-4 left-4 right-4 space-y-1">
                      {analysis.warnings.map((w, i) => (
                        <div key={i} className="rounded-lg bg-red-500/80 backdrop-blur-sm px-3 py-1.5 text-xs font-medium">
                          {w}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Overlay: joint info */}
                  {analysis && (
                    <div className="absolute top-4 right-4 rounded-xl bg-black/60 backdrop-blur-sm px-3 py-2 text-xs space-y-1">
                      <div>척추 <span className="font-mono text-cyan-400">{analysis.spine_angle}°</span></div>
                      <div>왼팔 <span className="font-mono text-cyan-400">{analysis.left_elbow}°</span></div>
                      <div>오른팔 <span className="font-mono text-cyan-400">{analysis.right_elbow}°</span></div>
                      <div>손 위치 <span className="text-cyan-400">{HAND_HEIGHT_LABEL[analysis.hand_height] || '-'}</span></div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Controls */}
            <div className="mt-4 flex gap-3">
              {saved ? (
                <div className="flex-1 space-y-3">
                  <div className="rounded-xl bg-emerald-500/20 border border-emerald-500/30 p-4 text-center">
                    <div className="text-lg font-bold text-emerald-400">분석 결과가 저장되었습니다</div>
                    <div className="mt-1 text-xs text-emerald-300/70">
                      체크리스트 {Object.values(checklistStatus).filter((s) => s === 'success').length}/{session.checklist_items.length} 항목 완료
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => router.push(`/practicum/session/${sessionId}`)}
                      className="flex-1 rounded-xl bg-brand-600 py-3 font-semibold text-white hover:bg-brand-700 transition"
                    >
                      상세 결과 보기
                    </button>
                    <button
                      onClick={() => router.push('/practicum')}
                      className="flex-1 rounded-xl border border-slate-700 py-3 font-semibold text-slate-300 hover:bg-slate-800 transition"
                    >
                      목록으로
                    </button>
                  </div>
                </div>
              ) : !recording ? (
                <button
                  onClick={() => { connectWS(); setTimeout(startAnalysis, 1000); }}
                  disabled={!!cameraError}
                  className="flex-1 rounded-xl bg-teal-600 py-3.5 font-bold text-white hover:bg-teal-700 disabled:opacity-40 transition"
                >
                  실시간 분석 시작
                </button>
              ) : (
                <button
                  onClick={handleStop}
                  disabled={saving}
                  className="flex-1 rounded-xl bg-red-600 py-3.5 font-bold text-white hover:bg-red-700 disabled:opacity-50 transition"
                >
                  {saving ? '저장 중...' : '분석 종료 + 결과 저장'}
                </button>
              )}
            </div>
          </div>

          {/* Right: Checklist + Feedback */}
          <div className="space-y-4">
            {/* Checklist */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-300">체크리스트</h3>
                <span className="text-xs text-slate-500">{totalChecked}/{totalItems}</span>
              </div>
              <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
                {session.checklist_items.map((item) => {
                  const status = checklistStatus[item.id];
                  return (
                    <div key={item.id} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${
                      status === 'success' ? 'bg-emerald-500/10' : status === 'partial' ? 'bg-amber-500/10' : 'bg-slate-800/50'
                    }`}>
                      <span className={`h-2 w-2 shrink-0 rounded-full ${STATUS_COLOR[status] || 'bg-slate-600'}`} />
                      <span className={`flex-1 ${status === 'success' ? 'text-emerald-300' : 'text-slate-400'}`}>
                        {item.label}
                      </span>
                      {item.is_critical && <span className="text-[9px] text-red-400">필수</span>}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* AI Feedback */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
              <h3 className="mb-3 text-sm font-bold text-slate-300">AI 코칭</h3>
              {feedbacks.length === 0 ? (
                <div className="text-xs text-slate-600">분석 시작 후 AI 피드백이 표시됩니다...</div>
              ) : (
                <div className="space-y-2 max-h-[250px] overflow-y-auto">
                  {feedbacks.map((fb, i) => (
                    <div key={i} className="rounded-lg bg-slate-800/50 p-3">
                      {fb.alert && (
                        <div className="mb-1 text-[10px] font-bold text-amber-400">{fb.alert}</div>
                      )}
                      <p className="text-xs text-slate-300 leading-relaxed">{fb.feedback}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Stats */}
            {analysis && (
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl bg-slate-800/50 p-3 text-center">
                  <div className="text-xs text-slate-500">척추 각도</div>
                  <div className="text-lg font-bold text-cyan-400">{analysis.spine_angle}°</div>
                </div>
                <div className="rounded-xl bg-slate-800/50 p-3 text-center">
                  <div className="text-xs text-slate-500">양손 거리</div>
                  <div className="text-lg font-bold text-cyan-400">{(analysis.hand_distance * 100).toFixed(0)}cm</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
