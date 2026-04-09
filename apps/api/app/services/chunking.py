"""청킹 전략 — 문단 기반 + 토큰 오버랩.

설계 원칙
--------
1. **문단 단위 1차 분할**: 빈 줄(`\\n\\n`)과 목록/헤딩 구분자를 경계로 사용
2. **목표 토큰 범위**: `chunk_target_tokens`(기본 800) 전후, 최소/최대 범위 준수
3. **오버랩**: 인접 청크끼리 `chunk_overlap_tokens`(기본 150) 만큼 겹치게 함 → 문맥 손실 방지
4. **과도하게 긴 문단**: 문장 단위 재분할(한국어 `. ! ?` + 줄바꿈), 그래도 넘치면 강제 split
5. **짧은 꼬리 청크**: 직전 청크에 병합하거나 독립 유지

토큰 카운트
----------
tiktoken이 설치되어 있으면 `cl100k_base`로 정확히 세고, 없으면 단어/문자 기반 근사.
한국어는 cl100k_base에서 1 한글 ≈ 1~2 토큰 정도로 대략 일치.

본 모듈은 외부 의존성 없이 순수 함수로 구성되며 단위 테스트 가능.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


# === 토큰 카운터 (tiktoken lazy import + fallback) ===


@lru_cache(maxsize=1)
def _get_tokenizer():
    """tiktoken encoder 싱글톤. 실패 시 None."""
    try:
        import tiktoken  # type: ignore

        return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:  # noqa: BLE001
        logger.warning("tiktoken unavailable, falling back to word-based count: %s", exc)
        return None


def count_tokens(text: str) -> int:
    """토큰 수 카운트. tiktoken이 없으면 근사값 반환."""
    if not text:
        return 0
    enc = _get_tokenizer()
    if enc is not None:
        return len(enc.encode(text))
    # Fallback 근사: 한글은 글자당 ~1토큰, 영문은 단어당 ~1.3토큰
    words = len(text.split())
    korean_chars = sum(1 for c in text if "\uac00" <= c <= "\ud7a3")
    return max(int(words * 1.3), korean_chars)


# === 자료구조 ===


@dataclass(frozen=True)
class Chunk:
    """청킹 결과 1건."""

    index: int
    content: str
    token_count: int
    char_count: int
    metadata: dict[str, Any]


# === 분할 유틸 ===

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")
_HEADING_RE = re.compile(r"^(#{1,6}\s|\d+\.\s|[가-힣]\.\s|[IVX]+\.\s)", re.MULTILINE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.!\?])\s+|\n")


def split_into_paragraphs(text: str) -> list[str]:
    """빈 줄 / 헤딩을 기준으로 문단 분할."""
    if not text:
        return []
    normalized = text.replace("\r\n", "\n").strip()
    # 1차: 이중 개행
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT_RE.split(normalized) if p.strip()]
    return paragraphs


def split_into_sentences(text: str) -> list[str]:
    """문장 단위 분할 — 긴 문단을 더 잘게 쪼갤 때 사용."""
    if not text:
        return []
    parts = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return parts


def _force_split_long_text(text: str, max_tokens: int) -> list[str]:
    """문장 분할로도 너무 긴 텍스트 → 토큰 수 기준 강제 분할."""
    enc = _get_tokenizer()
    if enc is not None:
        ids = enc.encode(text)
        chunks: list[str] = []
        for i in range(0, len(ids), max_tokens):
            chunks.append(enc.decode(ids[i : i + max_tokens]))
        return chunks
    # Fallback: 공백 기준 근사 분할
    words = text.split()
    approx = max(1, max_tokens)
    out = []
    for i in range(0, len(words), approx):
        out.append(" ".join(words[i : i + approx]))
    return out


# === 핵심 청킹 알고리즘 ===


def chunk_text(
    text: str,
    *,
    target_tokens: int | None = None,
    overlap_tokens: int | None = None,
    min_tokens: int | None = None,
    max_tokens: int | None = None,
) -> list[Chunk]:
    """텍스트를 문단 기반 + 오버랩으로 청킹.

    알고리즘
    --------
    1. 문단으로 1차 분할
    2. 토큰 수가 max_tokens 초과인 문단은 문장/강제 분할
    3. 문단을 순차적으로 누적하다가 target_tokens에 도달하면 청크 확정
    4. 다음 청크는 직전 청크 꼬리의 overlap_tokens 만큼을 prefix로 가짐
    5. min_tokens보다 짧은 꼬리 청크는 이전 청크에 병합

    Returns
    -------
    list[Chunk]
    """
    target = target_tokens or settings.chunk_target_tokens
    overlap = overlap_tokens or settings.chunk_overlap_tokens
    min_t = min_tokens or settings.chunk_min_tokens
    max_t = max_tokens or settings.chunk_max_tokens

    paragraphs = split_into_paragraphs(text)
    if not paragraphs:
        return []

    # 문단 정제: 너무 긴 문단은 문장 → 강제 분할로 쪼갠다
    normalized_paragraphs: list[str] = []
    for p in paragraphs:
        tc = count_tokens(p)
        if tc <= max_t:
            normalized_paragraphs.append(p)
            continue
        sentences = split_into_sentences(p)
        current = ""
        current_tc = 0
        for s in sentences:
            stc = count_tokens(s)
            if stc > max_t:
                # 단일 문장이 상한 초과 → 강제 분할
                if current:
                    normalized_paragraphs.append(current)
                    current, current_tc = "", 0
                for sub in _force_split_long_text(s, max_t):
                    normalized_paragraphs.append(sub)
                continue
            if current_tc + stc > max_t:
                normalized_paragraphs.append(current)
                current, current_tc = s, stc
            else:
                current = f"{current} {s}".strip() if current else s
                current_tc += stc
        if current:
            normalized_paragraphs.append(current)

    # 문단을 순회하며 target_tokens 근처로 묶음
    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_tokens = 0
    chunk_index = 0

    def _emit(contents: list[str]) -> None:
        nonlocal chunk_index
        content = "\n\n".join(contents).strip()
        if not content:
            return
        chunks.append(
            Chunk(
                index=chunk_index,
                content=content,
                token_count=count_tokens(content),
                char_count=len(content),
                metadata={"strategy": "paragraph+overlap"},
            )
        )
        chunk_index += 1

    for p in normalized_paragraphs:
        ptc = count_tokens(p)
        # 이 문단을 추가하면 target을 넘는 경우 → 현재 버퍼 확정
        if buffer and buffer_tokens + ptc > target:
            _emit(buffer)
            # 오버랩: 마지막 청크의 꼬리 일부를 다음 청크의 시작에 포함
            tail = _tail_overlap(buffer, overlap)
            buffer = list(tail)
            buffer_tokens = sum(count_tokens(x) for x in buffer)
        buffer.append(p)
        buffer_tokens += ptc

    # 마지막 청크 처리
    if buffer:
        # 너무 짧으면 이전 청크에 병합
        if chunks and buffer_tokens < min_t:
            last = chunks[-1]
            merged_content = last.content + "\n\n" + "\n\n".join(buffer)
            chunks[-1] = Chunk(
                index=last.index,
                content=merged_content,
                token_count=count_tokens(merged_content),
                char_count=len(merged_content),
                metadata=last.metadata,
            )
        else:
            _emit(buffer)

    return chunks


def _tail_overlap(paragraphs: list[str], overlap_tokens: int) -> list[str]:
    """문단 리스트의 꼬리에서 overlap_tokens 만큼을 추출해 반환."""
    if overlap_tokens <= 0 or not paragraphs:
        return []
    tail: list[str] = []
    acc = 0
    for p in reversed(paragraphs):
        tc = count_tokens(p)
        if acc + tc > overlap_tokens and tail:
            break
        tail.insert(0, p)
        acc += tc
    return tail
