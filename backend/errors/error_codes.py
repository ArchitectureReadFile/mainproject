from enum import Enum


class ErrorCode(Enum):
    """
    (에러코드, HTTP 상태코드, 메시지) 형식으로 정의합니다.

    에러코드 prefix 규칙:
      AUTH      : 인증/인가 (토큰, 세션)
      USER      : 사용자 계정 (가입, 로그인, 정보)
      EMAIL     : 이메일 발송 및 인증 코드
      DOC       : 문서 업로드 및 PDF 처리
      LLM       : LLM 요약 처리
      SUM       : 요약 결과 조회
      FILE      : 파일 다운로드
      PRECEDENT : RAG 판례 관리
      CHAT      : 채팅 세션 및 메시지 처리
    """

    @property
    def code(self) -> str:
        return self.value[0]

    @property
    def status_code(self) -> int:
        return self.value[1]

    @property
    def message(self) -> str:
        return self.value[2]

    # ── 인증 (AUTH) ──────────────────────────────────────────────────────────
    AUTH_TOKEN_MISSING = ("AUTH_001", 401, "로그인이 필요합니다.")
    AUTH_TOKEN_INVALID = ("AUTH_002", 401, "유효하지 않은 인증 토큰입니다.")
    AUTH_REFRESH_TOKEN_MISSING = ("AUTH_003", 401, "리프레시 토큰이 없습니다.")
    AUTH_REFRESH_TOKEN_EXPIRED = (
        "AUTH_004",
        401,
        "유효하지 않거나 만료된 리프레시 토큰입니다. 다시 로그인해주세요.",
    )
    AUTH_REFRESH_TOKEN_INVALID = ("AUTH_005", 401, "유효하지 않은 리프레시 토큰입니다.")
    AUTH_USER_INVALID = ("AUTH_006", 401, "유효하지 않은 사용자입니다.")
    AUTH_FORBIDDEN = ("AUTH_007", 403, "권한이 없습니다.")

    # ── 사용자 (USER) ────────────────────────────────────────────────────────
    USER_NOT_FOUND = ("USER_001", 404, "사용자를 찾을 수 없습니다.")
    USER_ACCOUNT_NOT_FOUND = (
        "USER_002",
        404,
        "해당 이메일로 가입된 계정 정보를 찾을 수 없습니다.",
    )
    USER_INACTIVE = ("USER_003", 403, "비활성화된 계정입니다.")
    USER_INVALID_CREDENTIALS = (
        "USER_004",
        401,
        "이메일 또는 비밀번호가 올바르지 않습니다.",
    )
    USER_EMAIL_ALREADY_EXISTS = ("USER_005", 409, "이미 사용 중인 이메일입니다.")
    USER_USERNAME_ALREADY_EXISTS = ("USER_006", 409, "이미 사용 중인 닉네임입니다.")
    USER_PASSWORD_TOO_LONG = (
        "USER_007",
        422,
        "비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.",
    )
    USER_EMAIL_NOT_VERIFIED = (
        "USER_008",
        401,
        "이메일 인증이 완료되지 않았거나 인증 시간이 초과되었습니다.",
    )
    USER_RATE_LIMIT_EXCEEDED = (
        "USER_009",
        429,
        "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.",
    )
    USER_DEACTIVATE_PENDING = (
        "USER_010",
        403,
        "탈퇴 대기 중인 계정입니다. 로그인을 진행하여 비활성화를 해제하시겠습니까?",
    )

    # ── 이메일 (EMAIL) ───────────────────────────────────────────────────────
    EMAIL_SEND_FAILED = (
        "EMAIL_001",
        500,
        "이메일 발송에 실패했습니다. 이메일 주소를 확인해주세요.",
    )
    EMAIL_CODE_NOT_FOUND = (
        "EMAIL_002",
        400,
        "인증 코드가 만료되었거나 존재하지 않습니다.",
    )
    EMAIL_CODE_MISMATCH = ("EMAIL_003", 400, "인증 코드가 일치하지 않습니다.")
    EMAIL_CONFIG_INVALID = ("EMAIL_004", 500, "서버의 이메일 설정이 올바르지 않습니다.")

    # ── 문서 (DOC) ───────────────────────────────────────────────────────────
    DOC_NOT_FOUND = ("DOC_001", 404, "문서를 찾을 수 없습니다.")
    DOC_PDF_TEXT_TOO_SHORT = (
        "DOC_002",
        422,
        "PDF에서 충분한 텍스트를 추출할 수 없습니다. 스캔본이거나 텍스트 레이어가 없는 문서일 수 있습니다.",
    )
    DOC_PDF_PARSE_FAILED = ("DOC_003", 422, "PDF 파일을 읽을 수 없습니다.")
    DOC_INVALID_FILE_TYPE = ("DOC_004", 415, "PDF 파일만 업로드 가능합니다.")
    DOC_FILE_TOO_LARGE = ("DOC_005", 413, "파일 크기는 20MB 이하여야 합니다.")
    DOC_INTERNAL_PARSE_ERROR = (
        "DOC_006",
        500,
        "문서 처리 중 서버 내부 오류가 발생했습니다.",
    )
    DOC_ALREADY_DELETE_PENDING = ("DOC_007", 409, "이미 삭제 요청된 문서입니다.")
    DOC_NOT_DELETE_PENDING = ("DOC_008", 400, "삭제 요청 상태가 아닙니다.")
    DOC_NOT_PENDING_REVIEW = ("DOC_009", 409, "승인 대기 상태의 문서가 아닙니다.")

    # ── LLM 요약 (LLM) ───────────────────────────────────────────────────────
    LLM_EMPTY_PAGES = ("LLM_001", 422, "텍스트 추출 결과가 비어 있습니다.")
    LLM_ALL_PROFILES_FAILED = (
        "LLM_002",
        502,
        "Ollama 요약 요청이 모든 프로파일에서 실패했습니다.",
    )
    LLM_CONNECT_FAILED = ("LLM_003", 503, "LLM 서버와 통신할 수 없습니다.")
    LLM_PROCESS_TIMEOUT = ("LLM_004", 504, "LLM 처리 시간이 초과되었습니다.")

    # ── 요약 결과 (SUM) ──────────────────────────────────────────────────────
    SUM_NOT_FOUND = ("SUM_001", 404, "요약을 찾을 수 없습니다.")

    # ── 파일 다운로드 (FILE) ─────────────────────────────────────────────────
    FILE_NOT_FOUND = ("FILE_001", 404, "파일을 찾을 수 없습니다.")

    # ── 판례 (PRECEDENT) ─────────────────────────────────────────────────────
    PRECEDENT_NOT_FOUND = ("PRECEDENT_001", 404, "판례를 찾을 수 없습니다.")
    PRECEDENT_DUPLICATE_URL = ("PRECEDENT_002", 409, "이미 등록된 판례 URL입니다.")
    PRECEDENT_INVALID_URL = ("PRECEDENT_003", 422, "유효하지 않은 URL 형식입니다.")
    PRECEDENT_DOMAIN_NOT_ALLOWED = (
        "PRECEDENT_004",
        422,
        "허용되지 않은 도메인입니다. 등록 가능한 판례 사이트의 URL만 입력해주세요.",
    )

    # ── 채팅 (CHAT) ──────────────────────────────────────────────────────────
    CHAT_ROOM_NOT_FOUND = ("CHAT_001", 404, "채팅방을 찾을 수 없습니다.")
    CHAT_UNAUTHORIZED = ("CHAT_002", 403, "채팅방에 대한 접근 권한이 없습니다.")
    CHAT_FILE_PARSE_FAILED = ("CHAT_003", 500, "채팅 파일 파싱 중 오류가 발생했습니다.")
    CHAT_HISTORY_LOAD_FAILED = (
        "CHAT_004",
        500,
        "대화 기록을 불러오는 중 오류가 발생했습니다.",
    )

    # ── 워크스페이스 (GROUP) ─────────────────────────────────────────────────
    GROUP_NOT_FOUND = ("GROUP_001", 404, "워크스페이스를 찾을 수 없습니다.")
    GROUP_OWNER_LIMIT = ("GROUP_002", 409, "이미 소유한 워크스페이스가 있습니다.")
    GROUP_NOT_PREMIUM = ("GROUP_003", 403, "프리미엄 구독이 필요합니다.")
    GROUP_NOT_OWNER = ("GROUP_004", 403, "워크스페이스 소유자만 가능합니다.")
    GROUP_ALREADY_DELETE_PENDING = (
        "GROUP_005",
        409,
        "이미 삭제 요청된 워크스페이스입니다.",
    )
    GROUP_NOT_DELETE_PENDING = ("GROUP_006", 400, "삭제 요청 상태가 아닙니다.")
    GROUP_RESTORE_OWNER_LIMIT = (
        "GROUP_007",
        409,
        "이미 소유한 활성 워크스페이스가 있어 복구할 수 없습니다.",
    )
    GROUP_MEMBER_NOT_FOUND = ("GROUP_008", 404, "멤버를 찾을 수 없습니다.")
    GROUP_MEMBER_ALREADY_EXISTS = ("GROUP_009", 409, "이미 그룹에 속한 사용자입니다.")
    GROUP_CANNOT_CHANGE_OWNER_ROLE = (
        "GROUP_010",
        403,
        "OWNER 권한은 오너 양도를 통해서만 변경할 수 있습니다.",
    )
    GROUP_CANNOT_REMOVE_OWNER = ("GROUP_011", 403, "OWNER는 추방할 수 없습니다.")
    GROUP_TRANSFER_TO_SELF = (
        "GROUP_012",
        400,
        "본인에게는 해당 작업을 수행할 수 없습니다.",
    )
    GROUP_NOT_ADMIN_OR_OWNER = ("GROUP_013", 403, "OWNER 또는 ADMIN만 가능합니다.")
    GROUP_CANNOT_CHANGE_SELF_ROLE = (
        "GROUP_014",
        400,
        "본인의 권한은 변경할 수 없습니다.",
    )
    GROUP_ADMIN_CANNOT_PROMOTE = (
        "GROUP_015",
        403,
        "ADMIN은 ADMIN 이상의 권한을 부여할 수 없습니다.",
    )
    GROUP_TRANSFER_TARGET_NOT_PREMIUM = (
        "GROUP_016",
        403,
        "프리미엄 구독자에게만 오너를 양도할 수 있습니다.",
    )
    GROUP_CANNOT_REMOVE_SELF = (
        "GROUP_017",
        403,
        "자기 자신은 그룹에서 제거할 수 없습니다.",
    )
    GROUP_CANNOT_INVITE_SELF = (
        "GROUP_018",
        403,
        "자기 자신은 그룹에 초대할 수 없습니다.",
    )
    GROUP_NOT_ACTIVE = ("GROUP_019", 400, "활성 상태의 그룹이 아닙니다.")
    GROUP_TRANSFER_TARGET_ALREADY_OWNER = (
        "GROUP_020",
        409,
        "해당 사용자는 이미 다른 워크스페이스의 오너입니다.",
    )
