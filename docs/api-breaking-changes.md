# API Breaking Changes Log

Breaking change 감지 시 `scripts/check_api_contracts.py`가 경고한다.
의도적인 변경이라면 `--update`로 스냅샷 갱신 후 이 파일에 기록한다.

## 형식

```
## [날짜] [버전] — 제목

**변경 내용**
- ...

**영향 범위**
- apps/web 어디 / 어떤 화면

**Migration**
1. ...
```

---

## 2026-04-16 v0.9 — 통합 에러 포맷 도입

**변경 내용**
- 모든 에러 응답이 `{error: {code, message, details?, request_id?}}` 구조로 통일
- 기존 `{detail: "..."}` 형태는 상위 호환을 위해 message로 매핑되나 프론트는 새 구조 사용 권장

**영향 범위**
- `apps/web/src/lib/api.ts` — `parseApiError()` 헬퍼로 일관 처리
- 모든 에러 토스트/인라인 메시지

**Migration**
1. 프론트에서 `response.detail` 직접 참조하던 코드를 `parseApiError(response)`로 교체
2. Zod `ErrorResponseSchema`로 runtime validation 적용

---

## 2026-04-16 v0.9 — Rate limit 응답 (429) 추가

**변경 내용**
- 고빈도 요청 시 429 + `Retry-After` 헤더 반환 (기존: 무제한)

**영향 범위**
- 로그인/패스워드 재설정/AI API를 반복 호출하는 클라이언트

**Migration**
- 429 수신 시 `Retry-After` 초만큼 대기 후 재시도 로직 추가
