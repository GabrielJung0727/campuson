# Postman Collection — CampusON API

`CampusON.postman_collection.json` 파일을 Postman 또는 Hoppscotch에 import해서 사용합니다.

## Import 방법

### Postman
1. Postman 실행 → **Import** 버튼
2. `CampusON.postman_collection.json` 선택
3. Collection 좌측에 "CampusON API (Week 1)"이 표시됨

### Hoppscotch (오픈소스)
1. <https://hoppscotch.io> 접속
2. **Collections** 패널 → **Import** → Postman v2.1
3. 동일 파일 선택

## 사용 흐름

1. **Auth → Register (Student)** 실행
   - Tests 스크립트가 응답에서 `access_token`/`refresh_token`/`user.id`를 자동으로
     컬렉션 변수에 저장합니다.
2. 이후 모든 요청은 자동으로 `Authorization: Bearer {{accessToken}}`을 사용합니다.
3. **Diagnostic → Start Diagnostic** → **Submit Diagnostic** 순서로 진단 테스트.
4. **Learning History → Submit Answer** 로 풀이 제출.
5. **AI → QA / Explain** 으로 LLM 호출 (기본 Mock 모드).

## 컬렉션 변수

| Key | 설명 |
| --- | --- |
| `baseUrl` | 기본 `http://localhost:8000/api/v1` |
| `accessToken` | Register/Login 후 자동 설정 |
| `refreshToken` | Register/Login 후 자동 설정 |
| `userId` | 본인 UUID |
| `testId` | 진단 테스트 시작 후 자동 설정 |
| `questionId` | 진단 첫 문항 또는 수동 지정 |
| `historyId` | 풀이 제출 후 자동 설정 |

## CSV Bulk Upload 사용 시

`Questions → Bulk Upload CSV` 요청은 form-data의 `file` 필드에
`data/seed/questions_seed.csv`를 첨부합니다. Postman에서 file path를 직접
프로젝트 루트 기준 절대 경로로 지정해주세요.

## Mock vs Real LLM

기본 환경에서는 `LLM_PROVIDER=mock`이라 AI 응답이 결정론적입니다.
실제 Claude/OpenAI를 사용하려면 `.env`에서:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

설정 후 서버를 재시작하세요.
