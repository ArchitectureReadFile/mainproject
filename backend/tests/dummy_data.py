from datetime import date

# -------------------------------------------------------------------
# DB 모델 픽스처용 데이터
# -------------------------------------------------------------------

users = [
    {
        "id": 1,
        "email": "testuser@example.com",
        "username": "테스트유저",
        "password": "password123!",
        "role": "GENERAL",
        "is_active": True,
    },
    {
        "id": 2,
        "email": "admin@example.com",
        "username": "관리자",
        "password": "hashed_admin_password!",
        "role": "ADMIN",
        "is_active": True,
    },
]

documents = [
    {
        "id": 101,
        "user_id": 1,
        "document_url": "https://s3.example.com/docs/doc_101.pdf",
        "status": "DONE",
    },
    {
        "id": 102,
        "user_id": 2,
        "document_url": "https://s3.example.com/docs/doc_102.pdf",
        "status": "PROCESSING",
    },
]

summaries = [
    {
        "id": 1,
        "document_id": 101,
        "case_number": "2023다12345",
        "case_name": "손해배상(기)",
        "court_name": "대법원",
        "judgment_date": date(2023, 10, 1),
        "summary_title": "손해배상 청구 사건 요약",
        "summary_main": "본 사건은 불법행위로 인한 손해배상 청구에 관한 대법원 판결입니다.",
        "plaintiff": "홍길동",
        "defendant": "김철수",
        "facts": "피고는 원고에게 폭행을 가하여 상해를 입혔음.",
        "judgment_order": "피고는 원고에게 금 10,000,000원을 지급하라.",
        "judgment_reason": "증거에 비추어 볼 때 피고의 불법행위가 인정됨.",
        "related_laws": "민법 제750조",
    }
]

# -------------------------------------------------------------------
# API 요청 Payload 및 테스트 데이터
# -------------------------------------------------------------------

login_data = {
    "payload": {"email": "testuser@example.com", "password": "password123!"},
    "wrong_password_payload": {
        "email": "testuser@example.com",
        "password": "wrong_password_123",
    },
    "inactive_user": {
        "email": "inactive@example.com",
        "username": "비활성유저",
        "password": "password123!",
        "is_active": False,
    },
}

signup_data = {
    "payload": {
        "email": "newuser@example.com",
        "username": "신규유저",
        "password": "newpassword123!",
    }
}

username_update_data = {"payload": {"username": "변경된유저"}}

email_verification_data = {
    "payload": {
        "valid_email": "verify@example.com",
        "valid_code": "123456",
        "invalid_code": "000000",
    }
}

confirm_account_data = {
    "payload": {
        "email": "confirm@example.com",
        "unregistered_email": "notfound@example.com",
    }
}

password_reset_data = {
    "payload": {
        "email": "reset@example.com",
        "unregistered_email": "notfound@example.com",
        "new_password": "new_secure_password_456!",
    }
}

refresh_token_data = {"payload": {"unregistered_email": "notfound@example.com"}}

tokens = {
    "valid_access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlckBleGFtcGxlLmNvbSJ9.valid_sign",
    "expired_access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlckBleGFtcGxlLmNvbSIsImV4cCI6MTIzNDU2Nzg5MH0.expired_sign",
    "valid_refresh_token": "valid_refresh_token_string",
    "expired_refresh_token": "expired_refresh_token_string",
}
