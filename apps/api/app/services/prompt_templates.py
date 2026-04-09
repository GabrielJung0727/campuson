"""프롬프트 템플릿 시스템 — Day 6 4종 템플릿.

특징
----
- `system` + `user_template` 구조
- 학생의 학습 수준(`level`)과 학과(`department`)에 따른 톤 조정
- 한국어 보건의료 도메인 특화

확장 계획
--------
- Day 9 RAG 통합 시 `context_docs` 슬롯 추가
- Day 11 추천 엔진과 통합되어 학생별 history 컨텍스트 주입
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import AIRequestType, Department, Level


@dataclass(frozen=True)
class PromptTemplate:
    """단일 프롬프트 템플릿."""

    name: str
    request_type: AIRequestType
    system: str
    user_template: str

    def render(self, **kwargs: object) -> tuple[str, str]:
        """`system`, `user`를 만들어 반환."""
        try:
            user = self.user_template.format(**kwargs)
        except KeyError as exc:
            raise ValueError(
                f"Template '{self.name}' is missing required key: {exc}"
            ) from exc
        return self.system, user


# === 공통 톤 가이드 ===
def _level_guide(level: Level | None) -> str:
    if level == Level.BEGINNER:
        return (
            "학생은 BEGINNER 수준입니다. 핵심 용어부터 차근차근 설명하고, "
            "전문 용어는 풀어서 쓰며, 기억할 만한 비유를 1개 제시하세요."
        )
    if level == Level.ADVANCED:
        return (
            "학생은 ADVANCED 수준입니다. 핵심만 간결하게, 임상적 적용까지 포함해 "
            "심화 포인트 위주로 답하세요."
        )
    return (
        "학생은 INTERMEDIATE 수준입니다. 개념의 이유와 임상적 의미를 균형 있게 "
        "설명하세요."
    )


def _department_label(dept: Department | None) -> str:
    if dept == Department.NURSING:
        return "간호사 국가시험 대비 간호학과 학생"
    if dept == Department.PHYSICAL_THERAPY:
        return "물리치료사 국가시험 대비 물리치료학과 학생"
    if dept == Department.DENTAL_HYGIENE:
        return "치과위생사 국가시험 대비 치위생과 학생"
    return "보건계열 학생"


# === EXPLAIN: 문제 해설 생성 ===
EXPLAIN_TEMPLATE = PromptTemplate(
    name="explain_v1",
    request_type=AIRequestType.EXPLAIN,
    system=(
        "당신은 한국 보건의료 국가시험 대비 전문 튜터입니다. "
        "학생의 풀이 결과를 바탕으로 문제 해설을 제공합니다. "
        "정확성을 최우선으로 하고, 추측하거나 모르는 내용은 모른다고 말하세요. "
        "응답은 마크다운으로 작성하며 다음 4섹션을 포함합니다: "
        "**핵심 정답** / **왜 그런가** / **틀린 선지 분석** / **꼭 기억할 한 줄 요약**."
    ),
    user_template=(
        "{department_label}의 문제 해설 요청입니다.\n"
        "{level_guide}\n\n"
        "## 문제\n{question_text}\n\n"
        "## 선택지\n{choices_text}\n\n"
        "## 정답\n{correct_answer_text} (인덱스 {correct_answer_index})\n\n"
        "## 학생의 응답\n{selected_answer_text} (인덱스 {selected_answer_index})\n"
        "결과: {result_label}\n\n"
        "## 출처/배경 (참고용)\n{explanation_or_blank}\n\n"
        "위 정보를 바탕으로 해설을 작성해 주세요."
    ),
)


# === QA: 자유 질의응답 ===
QA_TEMPLATE = PromptTemplate(
    name="qa_v1",
    request_type=AIRequestType.QA,
    system=(
        "당신은 한국 보건의료 국가시험 대비 전문 튜터입니다. "
        "학생의 질문에 대해 정확하고 친절하게 답변합니다. "
        "확신할 수 없는 내용은 추측하지 말고 모른다고 말하거나 추가 학습을 권유하세요. "
        "답변은 한국어 마크다운으로 작성합니다."
    ),
    user_template=(
        "{department_label}의 질문입니다.\n"
        "{level_guide}\n\n"
        "## 질문\n{user_question}\n\n"
        "친절하지만 학술적으로 정확하게 답변해 주세요."
    ),
)


# === RECOMMEND: 학습 추천 ===
RECOMMEND_TEMPLATE = PromptTemplate(
    name="recommend_v1",
    request_type=AIRequestType.RECOMMEND,
    system=(
        "당신은 학습 코치입니다. 학생의 진단 결과와 취약영역을 바탕으로 "
        "다음 1주일의 학습 계획을 제안합니다. 구체적인 단원과 행동을 포함하세요."
    ),
    user_template=(
        "{department_label}의 학습 추천 요청입니다.\n"
        "{level_guide}\n\n"
        "## 진단 결과\n"
        "- 전체 정답률: {total_score_pct}%\n"
        "- 수준: {level_value}\n\n"
        "## 취약 영역 (priority 순)\n{weak_areas_text}\n\n"
        "위 정보를 바탕으로 다음 1주일의 학습 계획을 5개 단계로 제안해 주세요. "
        "각 단계는 (1) 학습 단원, (2) 권장 활동, (3) 예상 소요 시간을 포함합니다."
    ),
)


# === WEAKNESS_ANALYSIS: 취약 영역 분석 ===
WEAKNESS_ANALYSIS_TEMPLATE = PromptTemplate(
    name="weakness_analysis_v1",
    request_type=AIRequestType.WEAKNESS_ANALYSIS,
    system=(
        "당신은 학습 분석 전문가입니다. 학생의 풀이 통계를 보고 패턴을 식별하여 "
        "구체적인 약점과 개선 방향을 제시합니다."
    ),
    user_template=(
        "{department_label}의 학습 통계입니다.\n\n"
        "## 통계\n"
        "- 전체 정답률: {accuracy_pct}%\n"
        "- 총 시도: {total_attempts}회\n"
        "- 오답 분류 분포: {error_distribution}\n\n"
        "## 과목별 정답률\n{subject_breakdown_text}\n\n"
        "위 통계로부터 학생의 약점 패턴 3가지를 식별하고, 각 약점에 대한 "
        "구체적인 개선 액션을 제시해 주세요."
    ),
)


# === Registry ===
TEMPLATES: dict[AIRequestType, PromptTemplate] = {
    AIRequestType.EXPLAIN: EXPLAIN_TEMPLATE,
    AIRequestType.QA: QA_TEMPLATE,
    AIRequestType.RECOMMEND: RECOMMEND_TEMPLATE,
    AIRequestType.WEAKNESS_ANALYSIS: WEAKNESS_ANALYSIS_TEMPLATE,
}


def get_template(request_type: AIRequestType) -> PromptTemplate:
    """request_type으로 템플릿 조회."""
    template = TEMPLATES.get(request_type)
    if template is None:
        raise KeyError(f"No template registered for {request_type.value}")
    return template


# === 헬퍼 ===
def build_explain_context(
    *,
    question_text: str,
    choices: list[str],
    correct_answer: int,
    selected_answer: int | None,
    is_correct: bool | None,
    explanation: str | None,
    department: Department | None,
    level: Level | None,
) -> dict[str, str]:
    """EXPLAIN 템플릿용 컨텍스트 dict 빌더."""
    choices_text = "\n".join(
        f"  {i + 1}. {c}" for i, c in enumerate(choices)
    )
    if selected_answer is None:
        selected_label = "선택 없음"
        selected_index_str = "-"
        result_label = "미응답"
    else:
        selected_label = (
            choices[selected_answer]
            if 0 <= selected_answer < len(choices)
            else "(범위 밖)"
        )
        selected_index_str = str(selected_answer)
        result_label = "정답" if is_correct else "오답"

    return {
        "department_label": _department_label(department),
        "level_guide": _level_guide(level),
        "question_text": question_text,
        "choices_text": choices_text,
        "correct_answer_text": choices[correct_answer]
        if 0 <= correct_answer < len(choices)
        else "(범위 밖)",
        "correct_answer_index": str(correct_answer),
        "selected_answer_text": selected_label,
        "selected_answer_index": selected_index_str,
        "result_label": result_label,
        "explanation_or_blank": explanation or "(공식 해설 없음)",
    }


def build_qa_context(
    *,
    user_question: str,
    department: Department | None,
    level: Level | None,
) -> dict[str, str]:
    return {
        "department_label": _department_label(department),
        "level_guide": _level_guide(level),
        "user_question": user_question,
    }
