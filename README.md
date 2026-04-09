# 🎓 CampusON

> 경복대학교 보건계열(간호·물리치료·치위생) 학생 전용 AI 학습튜터링 플랫폼

진단 테스트와 RAG 기반 지식베이스를 활용하여 국가고시 대비 맞춤형 학습을 지원합니다.

## 🏗 모노레포 구조

```
campuson/
├── apps/
│   ├── web/              # Next.js 14 (TypeScript, Tailwind, shadcn/ui)
│   └── api/              # FastAPI + SQLAlchemy + Alembic
├── packages/
│   └── shared/           # 공유 타입 및 유틸리티
├── docs/
│   └── diagrams/         # ER 다이어그램, 아키텍처 다이어그램
├── scripts/              # 개발/배포 스크립트
├── docker-compose.yml    # PostgreSQL + Redis 로컬 환경
├── .env.example          # 환경 변수 템플릿
└── package.json          # 워크스페이스 루트
```

## 🚀 빠른 시작

### 1. 사전 요구사항

- Node.js 20+
- Python 3.11+
- Docker Desktop
- pnpm or npm 10+

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 필요한 값을 채워주세요
```

### 3. Docker로 PostgreSQL + Redis 띄우기

```bash
npm run docker:up
```

### 4. 백엔드 (FastAPI) 실행

```bash
cd apps/api
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head            # DB 마이그레이션
uvicorn app.main:app --reload   # http://localhost:8000
```

### 5. 프론트엔드 (Next.js) 실행

```bash
cd apps/web
npm install
npm run dev                     # http://localhost:3000
```

## 📚 문서

- [Notion 프로젝트 페이지](https://www.notion.so/CampusON-AI-33d3748c8e9e80de8a5ccf9e72a350b6)
- [ER 다이어그램](docs/diagrams/er-diagram.md)
- [API 문서](http://localhost:8000/docs) (서버 실행 후)

## 🧰 개발 명령어

| 명령어 | 설명 |
| --- | --- |
| `npm run docker:up` | PostgreSQL + Redis 컨테이너 시작 |
| `npm run docker:down` | 컨테이너 중지 |
| `npm run docker:logs` | 컨테이너 로그 확인 |
| `npm run lint` | 전체 ESLint 실행 |
| `npm run format` | Prettier 포맷팅 |
| `npm run api:migrate` | DB 마이그레이션 적용 |

## 🛡 권한 체계

- **Student** — 본인 학습 데이터만 열람
- **Professor** — 본인 학과 학생 데이터 열람
- **Admin** — 학교 단위 운영 데이터 열람
- **Developer** — 시스템 설정 및 로그 접근

자세한 내용은 [02. 사용자 역할 및 권한 체계](https://www.notion.so/33d3748c8e9e81518e0eff5bbfbd0b06)를 참고하세요.
