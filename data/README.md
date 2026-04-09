# 📚 data/

국가고시 원본 자료(PDF)와 시드 데이터를 보관하는 디렉토리입니다.

## 구조

```
data/
├── nursing/              # 간호사 국가시험 원본 PDF
├── physical_therapy/     # 물리치료사 국가시험 원본 PDF
├── dental_hygiene/       # 치과위생사 국가시험 원본 PDF
└── seed/                 # bulk-upload 테스트용 CSV (Git 추적)
    └── questions_seed.csv
```

## 추적 정책

| 경로 | Git 추적 | 비고 |
| --- | :---: | --- |
| `data/*/README.md` | ✅ | 학과별 안내 |
| `data/*/*.pdf` | ❌ | 저작권 — `.gitignore`로 제외, 로컬 보존만 |
| `data/seed/*.csv` | ✅ | 200문항 시드 CSV (bulk-upload 테스트 용도) |

## 활용 흐름

1. **수동 큐레이션 시드** (현재 — Day 3):
   `apps/api/scripts/seed_data/{nursing,physical_therapy,dental_hygiene}.py`에 정의된
   200문항을 `seed_questions.py`로 DB에 적재.

2. **PDF OCR 파이프라인** (TODO — Day 9):
   `apps/api/scripts/ocr_nursing_pdfs.py`의 placeholder를 정교화하여 원본 PDF에서
   기출문항/답안을 자동 추출 → CSV → bulk-upload 엔드포인트로 적재.

3. **bulk-upload 엔드포인트**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/questions/bulk-upload \
     -H "Authorization: Bearer <ADMIN_TOKEN>" \
     -F "file=@data/seed/questions_seed.csv"
   ```
