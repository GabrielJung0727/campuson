# Monorepo Governance (v0.9)

경계와 규칙을 명확히 하여 apps/packages 간 의존성 부패를 예방한다.

## 구조

```
campuson/
├── apps/
│   ├── api/          ← FastAPI 백엔드 (Python)
│   └── web/          ← Next.js 프론트 (TypeScript)
├── packages/
│   └── shared/       ← 프론트 공용 타입/스키마 (TypeScript)
└── scripts/          ← 빌드·생성·검사 스크립트
```

## 의존성 규칙

### ✅ 허용

| From → To | 조건 |
|---|---|
| `apps/web` → `packages/shared` | 런타임 의존 가능 |
| `apps/api` → `packages/shared` | ❌ (언어 다름) — 대신 `scripts/generate_api_types.py`가 shared로 타입 생성 |
| `scripts/` → `apps/api` | 빌드 타임만 |
| `scripts/` → `packages/shared` | 빌드 타임만 |

### 🚫 금지

- `packages/shared` → `apps/*` (상향 의존)
- `apps/web` → `apps/api` (직접 import — HTTP API 경유 필수)
- `apps/api` → `apps/web` (양방향 금지)
- `packages/shared` 내에서 다른 workspace 로 의존
- 3rd-party 런타임 디펜던시를 `packages/shared`에 추가 (타입만)

## packages/shared 원칙

1. **타입과 스키마만** — 실행 로직 최소화.
2. **API 응답 DTO만 export** — 프론트 전용 유틸은 `apps/web`으로.
3. **런타임 의존성은 zod만** — validation 외 런타임 import 금지.
4. **파일 하나가 300줄 넘으면 분할** — domain별 (auth.ts, questions.ts 등).

`packages/shared/src/index.ts`가 5백 줄을 넘으므로 점진적으로 다음처럼 분할:

```
packages/shared/src/
├── index.ts        ← re-export 허브만
├── enums.ts        ← Department/Role/UserStatus/Difficulty 등
├── auth.ts         ← Login/Register/Token/PasswordReset
├── questions.ts    ← Question/Filter/BulkUpload
├── diagnostic.ts   ← DiagnosticStart/Submit/Result
├── history.ts      ← LearningHistory/Wrong/Stats
├── ai.ts           ← AI Request/Log
├── kb.ts           ← KB Ingest/Search/Document
└── schemas/        ← Zod 런타임 검증
    ├── common.ts
    └── error.ts
```

## API 계약 변경 프로세스

1. `apps/api/app/schemas/*.py` Pydantic 스키마 변경
2. `npm run generate:types` 실행 → `packages/shared/src/generated/api-types.ts` 갱신
3. `npm run check:contracts` 로 breaking change 탐지
4. `packages/shared/src/index.ts` 또는 도메인 파일에 수작업 보정 (선택)
5. `apps/web` 타입 에러 전부 해결 후 PR

Breaking change 기준:
- 필드 삭제 / 타입 변경 / enum 값 삭제 / required→optional 전환
- Breaking이면 `docs/api-breaking-changes.md`에 기록 + migration 노트

## 공용 유틸 경계

- **백엔드 전용 유틸** → `apps/api/app/utils/`
- **프론트 전용 유틸** → `apps/web/src/lib/`
- **양측 중복 로직** → 원칙적으로 허용하지 않음. 꼭 필요하면 각 언어별 구현 후 테스트로 동작 동등성 검증.

## 테스트 스코프

| 테스트 | 위치 | 범위 |
|---|---|---|
| 단위 (unit) | `apps/api/tests/unit/` | 함수/서비스 순수 로직 |
| 통합 (integration) | `apps/api/tests/integration/` | API 엔드포인트 + DB |
| RBAC | `apps/api/tests/rbac/` | 역할별 권한 매트릭스 |
| WS | `apps/api/tests/websocket/` | 실시간 실습 채널 |
| RAG | `apps/api/tests/rag/` | KB 검색 품질 |
| LLM | `apps/api/tests/llm/` | 프롬프트 회귀 |
| E2E | `apps/web/e2e/` | Playwright — 브라우저 끝단 |
| 성능 | `apps/api/tests/performance/` | Locust |
| 보안 | `apps/api/tests/security/` | SQL-i/XSS/JWT/PII |

## CI 권장 파이프라인

```
lint → typecheck → generate:types → check:contracts → unit → integration → e2e → build
```

## 역할별 PR 체크리스트

- [ ] `packages/shared`를 변경했다면 `apps/web` 빌드 성공 확인
- [ ] API 스키마 변경 시 `generate:types` 실행하여 `api-types.ts` 동기화
- [ ] breaking change는 `docs/api-breaking-changes.md`에 기록
- [ ] 새 유틸은 올바른 경계에 위치 (api vs web vs shared)
- [ ] 테스트 추가/업데이트 — 해당 스코프에
