"""비동기 SMTP 이메일 발송 서비스.

특징
----
- `aiosmtplib` 기반 비동기 발송 (FastAPI 이벤트 루프 블로킹 없음)
- Gmail SMTP 기본 지원 (smtp.gmail.com:587 + STARTTLS)
- `smtp_enabled=false` 이면 MOCK 모드 (로그만 출력, 실제 발송 안 함)
- 발송 실패 시 예외를 **삼키고 로그만 남김** (이메일 장애가 API 응답을 막으면 안 됨)
- background task로 호출하면 응답 지연 없음
"""

from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    *,
    from_email: str | None = None,
    from_name: str | None = None,
) -> bool:
    """이메일 1건 발송.

    Returns
    -------
    bool
        발송 성공 여부. 실패해도 예외를 raise하지 않는다.
    """
    sender_email = from_email or settings.smtp_from_email
    sender_name = from_name or settings.smtp_from_name

    # MOCK 모드
    if not settings.smtp_enabled:
        logger.info(
            "[MOCK EMAIL] to=%s subject='%s' (smtp_enabled=false, not sent)",
            to,
            subject,
        )
        return True

    if not settings.smtp_host or not settings.smtp_user:
        logger.warning("SMTP not configured (smtp_host or smtp_user empty). Skipping.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        import aiosmtplib

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=False,
            start_tls=settings.smtp_use_tls,
            timeout=15,
        )
        logger.info("Email sent: to=%s subject='%s'", to, subject)
        return True
    except ImportError:
        logger.warning(
            "aiosmtplib not installed. Run `pip install aiosmtplib`. Falling back to MOCK."
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.exception("Email send failed: to=%s subject='%s' error=%s", to, subject, exc)
        return False
