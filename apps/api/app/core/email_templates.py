"""이메일 HTML 템플릿 — 4종.

1. verification_code_email  — 6자리 인증코드
2. welcome_email            — 회원가입 환영
3. password_reset_email     — 비밀번호 재설정 토큰
4. password_changed_email   — 비밀번호 변경 알림
"""

from __future__ import annotations

DEPT_LABEL = {
    "NURSING": "간호학과",
    "PHYSICAL_THERAPY": "물리치료학과",
    "DENTAL_HYGIENE": "치위생과",
}

_BASE_STYLE = """
<style>
  body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; margin: 0; padding: 0; background: #f8fafc; }
  .container { max-width: 520px; margin: 40px auto; background: #fff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; }
  .header { background: linear-gradient(135deg, #0284c7, #0369a1); padding: 32px 24px; text-align: center; color: #fff; }
  .header h1 { margin: 0; font-size: 24px; }
  .header p { margin: 8px 0 0; font-size: 13px; opacity: 0.85; }
  .body { padding: 32px 24px; color: #1e293b; line-height: 1.7; font-size: 15px; }
  .code-box { background: #f1f5f9; border: 2px dashed #94a3b8; border-radius: 12px; padding: 20px; text-align: center; margin: 24px 0; }
  .code { font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #0369a1; font-family: monospace; }
  .btn { display: inline-block; background: #0284c7; color: #fff !important; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 15px; margin: 16px 0; }
  .footer { padding: 20px 24px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #f1f5f9; }
  .warn { background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; border-radius: 0 8px 8px 0; margin: 16px 0; font-size: 13px; color: #991b1b; }
</style>
"""


def verification_code_email(name: str, code: str, expire_minutes: int = 10) -> str:
    """회원가입 이메일 인증코드."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_STYLE}</head><body>
<div class="container">
  <div class="header">
    <h1>CampusON</h1>
    <p>이메일 인증</p>
  </div>
  <div class="body">
    <p>{name}님, 안녕하세요!</p>
    <p>CampusON 회원가입을 위해 아래 인증코드를 입력해주세요.</p>
    <div class="code-box">
      <div class="code">{code}</div>
    </div>
    <p style="font-size:13px;color:#64748b;">
      이 코드는 <strong>{expire_minutes}분</strong> 동안 유효합니다.<br>
      본인이 요청하지 않았다면 이 메일을 무시해주세요.
    </p>
  </div>
  <div class="footer">
    경복대학교 보건계열 AI 학습튜터링 플랫폼<br>
    CampusON &copy; 2026
  </div>
</div>
</body></html>"""


def welcome_email(name: str, department: str) -> str:
    """회원가입 환영 메일 (인증 완료 후)."""
    dept_label = DEPT_LABEL.get(department, department)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_STYLE}</head><body>
<div class="container">
  <div class="header">
    <h1>CampusON</h1>
    <p>환영합니다!</p>
  </div>
  <div class="body">
    <p>{name}님, CampusON에 오신 것을 환영합니다! 🎉</p>
    <p><strong>{dept_label}</strong> 학생으로 등록이 완료되었습니다.</p>
    <p>지금부터 다음 기능을 이용할 수 있습니다:</p>
    <ul>
      <li>🧪 <strong>진단 테스트</strong> — AI가 학습 수준을 분석</li>
      <li>📝 <strong>맞춤형 문제 풀이</strong> — 취약영역 중심 추천</li>
      <li>💬 <strong>AI 튜터</strong> — 자유로운 질의응답</li>
      <li>📊 <strong>학습 리포트</strong> — 성과 추적</li>
    </ul>
    <p>먼저 <strong>진단 테스트</strong>를 응시하면 AI가 맞춤형 학습을 제공합니다.</p>
    <p style="text-align:center;">
      <a href="#" class="btn">CampusON 시작하기</a>
    </p>
  </div>
  <div class="footer">
    경복대학교 보건계열 AI 학습튜터링 플랫폼<br>
    CampusON &copy; 2026
  </div>
</div>
</body></html>"""


def password_reset_email(name: str, token: str, expire_minutes: int = 30) -> str:
    """비밀번호 재설정 토큰 메일."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_STYLE}</head><body>
<div class="container">
  <div class="header">
    <h1>CampusON</h1>
    <p>비밀번호 재설정</p>
  </div>
  <div class="body">
    <p>{name}님, 비밀번호 재설정이 요청되었습니다.</p>
    <p>아래 토큰을 사용하여 비밀번호를 재설정해주세요:</p>
    <div class="code-box">
      <div style="font-size:14px;font-family:monospace;word-break:break-all;color:#0369a1;">{token}</div>
    </div>
    <p style="font-size:13px;color:#64748b;">
      이 토큰은 <strong>{expire_minutes}분</strong> 동안 유효합니다.
    </p>
    <div class="warn">
      본인이 요청하지 않았다면 이 메일을 무시해주세요.<br>
      비밀번호는 변경되지 않습니다.
    </div>
  </div>
  <div class="footer">
    CampusON &copy; 2026
  </div>
</div>
</body></html>"""


def password_changed_email(name: str) -> str:
    """비밀번호 변경 완료 알림."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_STYLE}</head><body>
<div class="container">
  <div class="header">
    <h1>CampusON</h1>
    <p>보안 알림</p>
  </div>
  <div class="body">
    <p>{name}님, 비밀번호가 성공적으로 변경되었습니다.</p>
    <p>본인이 변경한 것이 맞다면 이 메일을 무시해도 됩니다.</p>
    <div class="warn">
      본인이 변경하지 않았다면 즉시 비밀번호를 재설정하고 관리자에게 문의하세요.
    </div>
  </div>
  <div class="footer">
    CampusON &copy; 2026
  </div>
</div>
</body></html>"""
