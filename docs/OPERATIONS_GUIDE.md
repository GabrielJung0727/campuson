# CampusON 운영 가이드

## 1. 시스템 아키텍처

```
[Vercel] → Next.js 14 (프론트엔드)
    ↓ API 호출
[Render/Fly.io] → FastAPI (백엔드)
    ↓ DB/Cache
[PostgreSQL 16 + pgvector] + [Redis 7]
    ↓ AI
[Anthropic Claude / OpenAI] (LLM + Embeddings)
```

## 2. 배포 절차

### Frontend (Vercel)
1. GitHub 연동 후 `apps/web` 디렉토리 지정
2. 환경 변수 설정: `NEXT_PUBLIC_API_URL` → Render API URL
3. 자동 배포 (main 브랜치 push 시)

### Backend (Render)
1. `render.yaml` 기반 자동 설정 또는 수동 Web Service 생성
2. Root Directory: `apps/api`
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. PostgreSQL + Redis 생성 후 환경 변수 연결

### DB 마이그레이션
```bash
# Render Shell 또는 SSH에서
cd apps/api
alembic upgrade head
```

## 3. 환경 변수 (프로덕션 필수)

| 변수 | 설명 | 필수 |
| --- | --- | :---: |
| `DATABASE_URL` | PostgreSQL asyncpg URL | O |
| `DATABASE_URL_SYNC` | PostgreSQL psycopg2 URL | O |
| `REDIS_URL` | Redis URL | O |
| `JWT_SECRET_KEY` | JWT 서명 키 (32자 이상 랜덤) | O |
| `ENV` | `production` | O |
| `CORS_ORIGINS` | Vercel 도메인 | O |
| `LLM_PROVIDER` | `anthropic` 또는 `mock` | O |
| `ANTHROPIC_API_KEY` | Claude API 키 | 실제 AI 사용 시 |
| `OPENAI_API_KEY` | OpenAI 키 (임베딩용) | 실제 RAG 사용 시 |
| `AUDIT_LOG_ENABLED` | `true` | 권장 |

## 4. 모니터링

### Health Check
- `GET /api/v1/health` — 리브니스
- `GET /api/v1/health/db` — DB 연결 확인

### 로그
- 구조화된 Python 로깅 (JSON 형식 변환 권장)
- AI 호출: `ai_request_logs` 테이블 (비용 추적)
- API 감사: `audit_logs` 테이블 (보안 추적)

### 주요 지표
- API 응답 시간 (p50, p95)
- AI 호출 비용 (input_tokens + output_tokens)
- DB 연결 풀 사용률
- 에러율 (5xx)

## 5. 백업 정책

### PostgreSQL
- Render: 자동 일일 백업 (7일 보존)
- 수동: `pg_dump` 주기적 실행

### Redis
- AOF(Append Only File) 활성화 (docker-compose에서 설정됨)
- 세션/캐시 데이터만이므로 유실 시 재생성 가능

## 6. 장애 대응

### API 서버 다운
1. Render 대시보드 → Logs 확인
2. 최근 배포 rollback
3. Health check 모니터링

### DB 연결 실패
1. Render PostgreSQL 상태 확인
2. 연결 풀 고갈 → `pool_size` 조정
3. Alembic migration 실패 → rollback

### AI 호출 실패
1. `ai_request_logs` 에서 `success=false` 필터
2. API 키 만료/한도 확인
3. Mock fallback 자동 동작 확인

## 7. 보안 운영

### 정기 점검 (월 1회)
- [ ] JWT_SECRET_KEY 회전 (필요 시)
- [ ] API 키 만료일 확인
- [ ] `audit_logs` 이상 접근 패턴 검토
- [ ] 의존성 보안 업데이트 (`pip audit`, `npm audit`)
- [ ] RBAC 정책 검증

### 개인정보
- 학생 이메일/학번 암호화 저장 (bcrypt for passwords)
- 로그에 민감 필드 마스킹 (AuditLogMiddleware)
- GDPR/PIPA 준수 데이터 보존 정책

## 8. 확장 방안

### 수평 확장
- Render: Worker 수 증가 또는 Pro plan
- DB: Read replica 추가
- Redis: Cluster 모드

### 학과 추가
1. `Department` enum에 새 학과 추가
2. Alembic migration으로 enum 확장
3. 시드 데이터 (문제 + KB) 적재
4. 프론트엔드 `DEPARTMENTS` 배열에 추가
