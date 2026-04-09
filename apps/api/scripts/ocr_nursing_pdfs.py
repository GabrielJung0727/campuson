"""국가시험 PDF OCR 파이프라인 (Day 3 — placeholder).

대상 파일
---------
- data/nursing/2026년도 제66회 간호사 국가시험 1교시.pdf
- data/nursing/2026년도 제66회 간호사 국가시험 2교시.pdf
- data/nursing/2026년도 제66회 간호사 국가시험 3교시.pdf
- data/nursing/2026년도 제66회 간호사 국가시험 1~3교시 최종답안.pdf

상태
----
🚧 **TODO** — 본 스크립트는 현재 OCR pipeline의 골격만 갖추고 있다. 실제 PDF는 모두 스캔본
이미지여서 Tesseract OCR로 처리해야 하지만, 다음 이슈가 있어 Day 3 범위에서는
**원본 파일 보존**과 **CSV 생성 골격**까지만 제공한다.

알려진 이슈
- 표 형식 답안표가 셀 단위로 깨끗하게 OCR되지 않음 (`--psm 6` 시도 → 셀 병합 손상)
- 한글 질문 본문은 원거리 한글 폰트 + 페이지 워터마크로 인해 정확도 ~70% 수준
- 5지선다 선택지는 보기 번호와 본문이 OCR 단계에서 분리되기 어려움

향후 전략 (Day 9 KB 적재 시 정교화)
1. 페이지 영역 사전 분할 (cropbox 기반): 답안표 영역 / 문제 영역 / 보기 영역
2. Tesseract 대신 EasyOCR 또는 PaddleOCR 한글 모델로 비교 벤치마크
3. LLM 후처리 단계 추가 (Claude로 OCR 결과 → 구조화된 JSON)
4. 학생/교수 검수 워크플로우 (생성된 문제는 PENDING_REVIEW 상태로 등록)

사용법 (현재 — placeholder)
```
cd apps/api
python -m scripts.ocr_nursing_pdfs --pdf "../../data/nursing/...1교시.pdf" --out out.csv
```
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


@dataclass
class OCRConfig:
    """OCR 실행 설정."""

    pdf_path: Path
    out_csv: Path
    dpi: int = 300
    lang: str = "kor+eng"
    psm: int = 6  # uniform block of text
    tesseract_cmd: str = DEFAULT_TESSERACT_PATH
    page_range: tuple[int, int] | None = None  # 1-indexed inclusive

    @property
    def is_answer_key(self) -> bool:
        return "답안" in self.pdf_path.name


@dataclass
class OCRResult:
    """OCR 결과 컨테이너."""

    page_count: int = 0
    extracted_pages: int = 0
    raw_text: list[str] = field(default_factory=list)
    parsed_questions: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_ocr(config: OCRConfig) -> OCRResult:
    """PDF를 페이지별로 OCR하여 raw text를 수집한다.

    Returns
    -------
    OCRResult
    """
    try:
        import fitz  # type: ignore
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "OCR 의존성이 설치되어 있지 않습니다. "
            "`pip install pymupdf pillow pytesseract` 후 다시 실행하세요."
        ) from exc

    if config.tesseract_cmd and Path(config.tesseract_cmd).exists():
        pytesseract.pytesseract.tesseract_cmd = config.tesseract_cmd

    result = OCRResult()
    doc = fitz.open(str(config.pdf_path))
    result.page_count = doc.page_count

    start, end = config.page_range or (1, doc.page_count)
    for i in range(start - 1, min(end, doc.page_count)):
        try:
            page = doc[i]
            pix = page.get_pixmap(dpi=config.dpi)
            img = Image.open(pix.tobytes("png"))  # type: ignore[arg-type]
            text = pytesseract.image_to_string(
                img, lang=config.lang, config=f"--psm {config.psm}"
            )
            result.raw_text.append(text)
            result.extracted_pages += 1
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"page {i + 1}: {exc}")

    doc.close()
    return result


def parse_answer_key(_raw_pages: list[str]) -> dict[tuple[int, int], int]:
    """답안표를 (교시, 문제번호) → 정답 번호 매핑으로 파싱.

    🚧 TODO: 표 OCR 결과에서 행 단위로 정규식 매칭 필요. 현재는 미구현.

    Returns
    -------
    dict
        예: {(1, 5): 3, (1, 6): 2, ...}
    """
    logger.warning("parse_answer_key is not yet implemented — returns empty dict")
    return {}


def parse_question_pages(_raw_pages: list[str]) -> list[dict]:
    """문제 본문 OCR 결과를 구조화된 dict 리스트로 파싱.

    🚧 TODO: 질문 시작 표지("1.", "2." 등) 기반 분할 + 보기("①~⑤") 추출 + LLM 후처리.
    """
    logger.warning("parse_question_pages is not yet implemented — returns empty list")
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Nursing PDF OCR placeholder")
    parser.add_argument("--pdf", type=Path, required=True, help="대상 PDF 경로")
    parser.add_argument("--out", type=Path, required=True, help="출력 CSV 경로")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument(
        "--tesseract", type=str, default=DEFAULT_TESSERACT_PATH, help="Tesseract 실행 파일 경로"
    )
    parser.add_argument(
        "--pages", type=str, default=None, help="페이지 범위 — 예: 5-11 (1-indexed)"
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"❌ PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    page_range = None
    if args.pages:
        a, b = args.pages.split("-")
        page_range = (int(a), int(b))

    config = OCRConfig(
        pdf_path=args.pdf,
        out_csv=args.out,
        dpi=args.dpi,
        tesseract_cmd=args.tesseract,
        page_range=page_range,
    )

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(f"🔍 OCR start: {args.pdf.name}")
    result = run_ocr(config)
    print(f"   pages={result.page_count} extracted={result.extracted_pages}")
    if result.errors:
        print(f"   ⚠️  {len(result.errors)} page errors")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(result.raw_text), encoding="utf-8")
    print(f"📝 raw text dumped → {args.out}")
    print(
        "🚧 TODO: parse_answer_key / parse_question_pages 구현 후 CSV 변환 단계 추가 필요"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
