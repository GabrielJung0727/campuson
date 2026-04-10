"""과제 시스템 + PDF→RAG + AI 문제 생성 라우터.

v0.2 P2 엔드포인트
-----------------
과제:
- POST   /assignments              — 과제 출제 (교수)
- GET    /assignments              — 내 과제 목록 (교수: 출제한, 학생: 배정된)
- GET    /assignments/{id}         — 과제 상세 + 제출 현황
- POST   /assignments/{id}/submit  — 과제 제출 (학생)
- PATCH  /assignments/{id}/status  — 과제 상태 변경 (PUBLISH/CLOSE)

PDF → RAG:
- POST   /kb/upload-pdf            — PDF 업로드 → OCR → KB 적재

AI 문제 생성:
- POST   /ai/generate-questions    — LLM으로 문제 자동 생성
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_active_user, require_roles
from app.core.llm import get_llm_gateway
from app.db.session import get_db
from app.models.assignment import Assignment, AssignmentStatus, AssignmentSubmission
from app.models.enums import Department, Difficulty, Role
from app.models.question import Question
from app.models.user import User
from app.schemas.common import MessageResponse

router = APIRouter(tags=["assignments"])


# === Schemas ===
class AssignmentCreateRequest(BaseModel):
    title: str = Field(..., max_length=200)
    description: str | None = None
    class_id: str | None = None
    question_ids: list[str] = Field(..., min_length=1, max_length=100)
    due_date: datetime | None = None
    publish: bool = False


class AssignmentResponse(BaseModel):
    id: str
    title: str
    description: str | None
    status: str
    total_questions: int
    due_date: str | None
    submission_count: int
    created_at: str


class SubmitAssignmentRequest(BaseModel):
    answers: list[dict] = Field(..., min_length=1)


class GenerateQuestionsRequest(BaseModel):
    department: Department
    subject: str = Field(..., min_length=1)
    unit: str | None = None
    difficulty: Difficulty = Difficulty.MEDIUM
    count: int = Field(default=10, ge=1, le=50)


class GeneratedQuestion(BaseModel):
    question_text: str
    choices: list[str]
    correct_answer: int
    explanation: str
    difficulty: str
    subject: str


# === 과제 CRUD ===
@router.post("/assignments", status_code=201, summary="과제 출제")
async def create_assignment(
    payload: AssignmentCreateRequest,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> AssignmentResponse:
    assignment = Assignment(
        professor_id=current_user.id,
        class_id=uuid.UUID(payload.class_id) if payload.class_id else None,
        department=current_user.department,
        title=payload.title,
        description=payload.description,
        status=AssignmentStatus.PUBLISHED if payload.publish else AssignmentStatus.DRAFT,
        question_ids=payload.question_ids,
        total_questions=len(payload.question_ids),
        due_date=payload.due_date,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return AssignmentResponse(
        id=str(assignment.id), title=assignment.title,
        description=assignment.description, status=assignment.status.value,
        total_questions=assignment.total_questions,
        due_date=assignment.due_date.isoformat() if assignment.due_date else None,
        submission_count=0, created_at=assignment.created_at.isoformat(),
    )


@router.get("/assignments", summary="과제 목록")
async def list_assignments(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentResponse]:
    if current_user.role in (Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER):
        stmt = select(Assignment).where(Assignment.professor_id == current_user.id)
    else:
        # 학생: 자기 학과의 PUBLISHED 과제
        stmt = select(Assignment).where(
            Assignment.department == current_user.department,
            Assignment.status == AssignmentStatus.PUBLISHED,
        )
    stmt = stmt.order_by(Assignment.created_at.desc()).limit(50)
    rows = list((await db.execute(stmt)).scalars().all())

    result = []
    for a in rows:
        sub_count = (await db.execute(
            select(AssignmentSubmission).where(AssignmentSubmission.assignment_id == a.id)
        )).scalars().all()
        result.append(AssignmentResponse(
            id=str(a.id), title=a.title, description=a.description,
            status=a.status.value, total_questions=a.total_questions,
            due_date=a.due_date.isoformat() if a.due_date else None,
            submission_count=len(sub_count), created_at=a.created_at.isoformat(),
        ))
    return result


@router.get("/assignments/{assignment_id}", summary="과제 상세")
async def get_assignment(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    assignment = await db.get(
        Assignment, assignment_id, options=[selectinload(Assignment.submissions)]
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # 학생에게는 문제 ID 목록 + 자기 제출 여부
    my_submission = None
    if current_user.role == Role.STUDENT:
        for sub in assignment.submissions:
            if sub.student_id == current_user.id:
                my_submission = {
                    "score": sub.score,
                    "total_correct": sub.total_correct,
                    "submitted_at": sub.submitted_at.isoformat(),
                }
                break

    return {
        "id": str(assignment.id),
        "title": assignment.title,
        "description": assignment.description,
        "status": assignment.status.value,
        "total_questions": assignment.total_questions,
        "question_ids": assignment.question_ids,
        "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
        "submission_count": len(assignment.submissions),
        "my_submission": my_submission,
    }


@router.post("/assignments/{assignment_id}/submit", status_code=201, summary="과제 제출")
async def submit_assignment(
    assignment_id: uuid.UUID,
    payload: SubmitAssignmentRequest,
    current_user: User = Depends(require_roles(Role.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None or assignment.status != AssignmentStatus.PUBLISHED:
        raise HTTPException(status_code=404, detail="Assignment not found or not published")

    if assignment.due_date and datetime.now(UTC) > assignment.due_date:
        raise HTTPException(status_code=400, detail="Assignment due date has passed")

    # 중복 제출 확인
    existing = await db.scalar(
        select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == current_user.id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already submitted")

    # 채점
    q_ids = [uuid.UUID(qid) for qid in assignment.question_ids]
    questions = {q.id: q for q in (await db.execute(select(Question).where(Question.id.in_(q_ids)))).scalars().all()}

    scored_answers = []
    correct = 0
    total_time = 0
    for ans in payload.answers:
        qid = uuid.UUID(ans.get("question_id", ""))
        q = questions.get(qid)
        if q is None:
            continue
        sel = int(ans.get("selected_choice", -1))
        is_correct = sel == q.correct_answer
        if is_correct:
            correct += 1
        time_sec = int(ans.get("time_spent_sec", 0))
        total_time += time_sec
        scored_answers.append({
            "question_id": str(qid),
            "selected_choice": sel,
            "is_correct": is_correct,
            "time_spent_sec": time_sec,
        })

    total = len(scored_answers)
    score = round(correct / total, 4) if total > 0 else 0.0

    submission = AssignmentSubmission(
        assignment_id=assignment_id,
        student_id=current_user.id,
        answers=scored_answers,
        total_correct=correct,
        total_questions=total,
        score=score,
        time_spent_sec=total_time,
    )
    db.add(submission)
    await db.flush()

    return {
        "score": score,
        "total_correct": correct,
        "total_questions": total,
        "time_spent_sec": total_time,
    }


@router.patch("/assignments/{assignment_id}/status", summary="과제 상태 변경")
async def update_assignment_status(
    assignment_id: uuid.UUID,
    new_status: str,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None or assignment.professor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    assignment.status = AssignmentStatus(new_status.upper())
    await db.flush()
    return MessageResponse(message=f"Status changed to {assignment.status.value}")


# === PDF → RAG ===
@router.post("/kb/upload-pdf", summary="PDF → OCR → RAG 자동 적재")
async def upload_pdf_to_rag(
    file: UploadFile = File(...),
    department: Department = Department.NURSING,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """PDF 업로드 → OCR → 청킹 → 임베딩 → KB 적재.

    현재 PyMuPDF로 텍스트 추출 시도 → 실패 시 pytesseract OCR.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF exceeds 50MB")

    # 텍스트 추출
    extracted_text = ""
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        pages_text = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages_text.append(text)
        doc.close()
        extracted_text = "\n\n".join(pages_text)
    except Exception:
        pass

    # PyMuPDF로 텍스트가 없으면 OCR 시도
    if len(extracted_text.strip()) < 50:
        try:
            import fitz
            import pytesseract
            from PIL import Image
            import io

            pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            doc = fitz.open(stream=content, filetype="pdf")
            ocr_pages = []
            for i, page in enumerate(doc):
                if i >= 20:  # 최대 20페이지
                    break
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img, lang="kor+eng")
                if text.strip():
                    ocr_pages.append(text)
            doc.close()
            extracted_text = "\n\n".join(ocr_pages)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"PDF 텍스트 추출 실패. Tesseract가 설치되어 있는지 확인하세요: {exc}"
            ) from exc

    if len(extracted_text.strip()) < 50:
        raise HTTPException(status_code=422, detail="PDF에서 충분한 텍스트를 추출할 수 없습니다.")

    # KB에 적재
    from app.services.kb_ingest_service import IngestRequest, ingest_document

    result = await ingest_document(
        db,
        IngestRequest(
            department=department,
            title=file.filename or "Uploaded PDF",
            content=extracted_text,
            source=f"PDF upload: {file.filename}",
            tags=["pdf-upload", department.value.lower()],
        ),
    )

    return {
        "message": "PDF 적재 완료",
        "document_id": str(result.document_id),
        "total_chunks": result.total_chunks,
        "total_tokens": result.total_tokens,
        "embedded_chunks": result.embedded_chunks,
        "text_length": len(extracted_text),
    }


# === AI 문제 생성 ===
@router.post("/ai/generate-questions", summary="AI 기반 국시 문제 자동 생성")
async def generate_questions(
    payload: GenerateQuestionsRequest,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """RAG 지식베이스를 참조하여 LLM으로 문제를 자동 생성.

    교수가 검수 후 문제은행에 등록할 수 있다.
    """
    gateway = get_llm_gateway()

    system = (
        "당신은 한국 보건의료 국가시험 문제 출제 전문가입니다. "
        "주어진 조건에 맞는 국가시험 형식의 객관식 5지선다 문제를 생성합니다. "
        "각 문제는 question_text, choices(5개), correct_answer(0-indexed), explanation을 포함합니다. "
        "JSON 배열로 응답하세요."
    )

    unit_text = f" > {payload.unit}" if payload.unit else ""
    user_prompt = (
        f"학과: {payload.department.value}\n"
        f"과목: {payload.subject}{unit_text}\n"
        f"난이도: {payload.difficulty.value}\n"
        f"문항 수: {payload.count}\n\n"
        f"위 조건에 맞는 국가시험 형식의 문제를 {payload.count}개 생성해주세요.\n"
        f"JSON 배열로 응답하세요:\n"
        f'[{{"question_text": "...", "choices": ["A","B","C","D","E"], '
        f'"correct_answer": 0, "explanation": "..."}}]'
    )

    try:
        result = await gateway.generate(system=system, user=user_prompt, max_tokens=4096)
        output = result.output_text

        # JSON 추출 시도
        import json
        import re

        json_match = re.search(r"\[.*\]", output, re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group())
        else:
            questions = [{"raw_output": output, "parse_failed": True}]

        return {
            "generated_count": len(questions),
            "department": payload.department.value,
            "subject": payload.subject,
            "difficulty": payload.difficulty.value,
            "questions": questions,
            "provider": gateway.provider_name.value,
            "model": gateway.model,
            "note": "교수 검수 후 POST /questions로 문제은행에 등록하세요.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM 문제 생성 실패: {exc}"
        ) from exc
