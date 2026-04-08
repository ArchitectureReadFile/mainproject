import json
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

groups = [
    {
        "id": 1,
        "owner_user_id": 1,
        "name": "테스트 워크스페이스",
        "description": "문서 테스트용 그룹",
        "status": "ACTIVE",
    },
    {
        "id": 2,
        "owner_user_id": 2,
        "name": "관리자 워크스페이스",
        "description": "관리자 문서 테스트용 그룹",
        "status": "ACTIVE",
    },
]

# document_type / category: Document 모델 컬럼 (source of truth)
# summary metadata의 document_type은 보조 기록 — 표시 기준 아님
documents = [
    {
        "id": 101,
        "group_id": 1,
        "uploader_user_id": 1,
        "original_filename": "doc_101.pdf",
        "stored_path": "/tmp/test_docs/doc_101.pdf",
        "processing_status": "DONE",
        "document_type": "소장",
        "category": "민사",
    },
    {
        "id": 102,
        "group_id": 2,
        "uploader_user_id": 2,
        "original_filename": "doc_102.pdf",
        "stored_path": "/tmp/test_docs/doc_102.pdf",
        "processing_status": "PROCESSING",
        "document_type": "미분류",
        "category": "미분류",
    },
    {
        "id": 103,
        "group_id": 1,
        "uploader_user_id": 1,
        "original_filename": "doc_103.pdf",
        "stored_path": "/tmp/test_docs/doc_103.pdf",
        "processing_status": "DONE",
        "document_type": None,  # 분류 미완료 — 미분류 목록 조회 대상
        "category": None,
    },
]

summaries = [
    {
        "id": 1,
        "document_id": 101,
        "summary_text": "원고가 불법행위로 인한 손해배상을 청구한 사건으로, 검토자는 사실관계와 손해배상 인정 범위를 먼저 확인할 필요가 있습니다.",
        "key_points": "불법행위 성립 여부가 핵심 쟁점입니다.\n손해배상 인정 범위와 액수를 확인해야 합니다.\n판단 근거가 되는 증거 관계를 우선 검토해야 합니다.",
        # metadata_json의 document_type은 보조 기록 — 응답/PDF 표시에 사용 안 함
        "metadata_json": json.dumps(
            {
                "document_type": "판결문",  # 구 legacy 값, 표시 기준 아님
                "case_number": "2023다12345",
                "case_name": "손해배상(기)",
                "court_name": "대법원",
                "judgment_date": str(date(2023, 10, 1)),
                "plaintiff": "홍길동",
                "defendant": "김철수",
            },
            ensure_ascii=False,
        ),
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
