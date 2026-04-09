# 🦴 physical_therapy/

물리치료사 국가시험 원본 PDF 보관 폴더.

## 파일 명명 규칙

PDF 파일을 이 폴더에 넣을 때 다음 형식을 권장합니다.

```
YYYY년도 제NN회 물리치료사 국가시험 1교시.pdf
YYYY년도 제NN회 물리치료사 국가시험 2교시.pdf
YYYY년도 제NN회 물리치료사 국가시험 최종답안.pdf
```

## 시험 구조 (참고)

물리치료사 국가시험은 보통 다음과 같이 구성됩니다.

| 교시 | 주요 과목 |
| :---: | --- |
| 1교시 | 의료관계법규, 공중보건학개론, 해부생리학, 운동학, 신경과학 |
| 2교시 | 물리치료진단평가학, 물리치료중재학(신경계/근골격/심폐/소아) |
| 실기 | 물리치료 실기 (별도 시행) |

## 주의

- 모든 PDF는 **저작권 보호**를 위해 `.gitignore`로 Git 추적에서 제외됩니다 (`data/physical_therapy/*.pdf`).
- 본 폴더는 `README.md`만 Git에 추적됩니다.
- 학습용 시드 데이터는 `apps/api/scripts/seed_data/physical_therapy.py`에 큐레이션되어 있습니다 (60문항).

## 향후 OCR 파이프라인

PDF를 자동으로 문제은행에 적재하는 작업은 Day 9 (KB 적재) 단계에서 정교화될 예정입니다.
현재는 `apps/api/scripts/ocr_nursing_pdfs.py`에 placeholder + TODO만 존재합니다.
