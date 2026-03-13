import os
import smtplib
from email.message import EmailMessage

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


def send_verification_email(to_email: str, code: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        raise ValueError("SMTP 설정이 누락되었습니다.")

    msg = EmailMessage()
    msg["Subject"] = "[ReadFile] 이메일 인증 코드 안내"
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    html_content = f"""
    <div style="font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; max-width: 500px; margin: 0 auto; padding: 30px; border: 1px solid #eaeaea; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <h2 style="color: #2c3e50; text-align: center; margin-bottom: 20px;">이메일 인증</h2>
        <p style="color: #555; font-size: 15px; line-height: 1.6; text-align: center;">
            안녕하세요.<br>
            요청하신 이메일 인증 코드입니다.<br>
            아래의 6자리 숫자를 입력해 주세요.
        </p>
        <div style="background-color: #f8f9fa; padding: 25px; text-align: center; margin: 30px 0; border-radius: 8px; border: 1px solid #eee;">
            <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #007bff;">{code}</span>
        </div>
        <p style="color: #888; font-size: 13px; text-align: center; line-height: 1.5;">
            이 코드는 <strong>3분</strong> 동안만 유효합니다.<br>
            본인이 요청하지 않으셨다면 이 이메일을 무시해 주세요.
        </p>
    </div>
    """
    msg.add_alternative(html_content, subtype="html")

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
