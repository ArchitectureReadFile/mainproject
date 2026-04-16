/**
 * 백엔드 errors/error_codes.py 와 1:1 대응되는 에러 코드 상수입니다.
 *
 * 사용 예시:
 *   import { ERROR_CODE } from "@/shared/lib/errors";
 *   if (error.code === ERROR_CODE.AUTH_TOKEN_MISSING) { ... }
 */

export const ERROR_CODE = {
  // ── 인증 (AUTH) ────────────────────────────────────────────
  AUTH_TOKEN_MISSING:           "AUTH_001",
  AUTH_TOKEN_INVALID:           "AUTH_002",
  AUTH_REFRESH_TOKEN_MISSING:   "AUTH_003",
  AUTH_REFRESH_TOKEN_EXPIRED:   "AUTH_004",
  AUTH_REFRESH_TOKEN_INVALID:   "AUTH_005",
  AUTH_USER_INVALID:            "AUTH_006",
  AUTH_FORBIDDEN:               "AUTH_007",

  // ── 사용자 (USER) ───────────────────────────────────────────
  USER_NOT_FOUND:               "USER_001",
  USER_ACCOUNT_NOT_FOUND:       "USER_002",
  USER_INACTIVE:                "USER_003",
  USER_INVALID_CREDENTIALS:     "USER_004",
  USER_EMAIL_ALREADY_EXISTS:    "USER_005",
  USER_USERNAME_ALREADY_EXISTS: "USER_006",
  USER_PASSWORD_TOO_LONG:       "USER_007",
  USER_EMAIL_NOT_VERIFIED:      "USER_008",
  USER_RATE_LIMIT_EXCEEDED:     "USER_009",

  // ── 이메일 (EMAIL) ──────────────────────────────────────────
  EMAIL_SEND_FAILED:            "EMAIL_001",
  EMAIL_CODE_NOT_FOUND:         "EMAIL_002",
  EMAIL_CODE_MISMATCH:          "EMAIL_003",

  // ── 문서 (DOC) ──────────────────────────────────────────────
  DOC_NOT_FOUND:                "DOC_001",
  DOC_PDF_TEXT_TOO_SHORT:       "DOC_002",
  DOC_PDF_PARSE_FAILED:         "DOC_003",
  DOC_INVALID_FILE_TYPE:        "DOC_004",
  DOC_FILE_TOO_LARGE:           "DOC_005",

  // ── LLM 요약 (LLM) ─────────────────────────────────────────
  LLM_EMPTY_PAGES:              "LLM_001",
  LLM_ALL_PROFILES_FAILED:      "LLM_002",

  // ── 요약 결과 (SUM) ─────────────────────────────────────────
  SUM_NOT_FOUND:                "SUM_001",

  // ── 파일 다운로드 (FILE) ────────────────────────────────────
  FILE_NOT_FOUND:               "FILE_001",

  // ── 플랫폼 동기화 (PLATFORM) ─────────────────────────────────
  PLATFORM_SYNC_CONFIG_MISSING: "PLATFORM_001",
  PLATFORM_SYNC_REQUEST_FAILED: "PLATFORM_002",
};

export function getErrorCode(error) {
  return error.response?.data?.code ?? null;
}

export function getErrorMessage(error, fallback = "요청에 실패했습니다.") {
  return error.response?.data?.message ?? fallback;
}

export function getErrorMessageByCode(code, fallback = "요청에 실패했습니다.") {
  const codeMessages = {
    [ERROR_CODE.AUTH_FORBIDDEN]: "권한이 없습니다.",
    [ERROR_CODE.USER_ACCOUNT_NOT_FOUND]: "해당 이메일로 가입된 계정 정보를 찾을 수 없습니다.",
    [ERROR_CODE.USER_INACTIVE]: "비활성화된 계정입니다. 관리자에게 문의해주세요.",
    [ERROR_CODE.USER_INVALID_CREDENTIALS]: "이메일 또는 비밀번호가 올바르지 않습니다.",
    [ERROR_CODE.USER_EMAIL_ALREADY_EXISTS]: "이미 사용 중인 이메일입니다.",
    [ERROR_CODE.USER_USERNAME_ALREADY_EXISTS]: "이미 사용 중인 닉네임입니다.",
    [ERROR_CODE.USER_PASSWORD_TOO_LONG]: "비밀번호는 72바이트 이하여야 합니다.",
    [ERROR_CODE.USER_EMAIL_NOT_VERIFIED]: "이메일 인증을 완료해주세요.",
    [ERROR_CODE.USER_RATE_LIMIT_EXCEEDED]: "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.",
    [ERROR_CODE.EMAIL_SEND_FAILED]: "인증번호 발송에 실패했습니다.",
    [ERROR_CODE.EMAIL_CODE_NOT_FOUND]: "인증번호가 만료되었거나 존재하지 않습니다.",
    [ERROR_CODE.EMAIL_CODE_MISMATCH]: "인증번호가 일치하지 않습니다.",
    [ERROR_CODE.DOC_NOT_FOUND]: "문서를 찾을 수 없습니다.",
    [ERROR_CODE.DOC_INVALID_FILE_TYPE]: "PDF, DOC, DOCX 파일만 업로드 가능합니다.",
    [ERROR_CODE.DOC_FILE_TOO_LARGE]: "파일 크기는 20MB 이하여야 합니다.",
    [ERROR_CODE.PLATFORM_SYNC_CONFIG_MISSING]: "공공 법령 Open API 설정이 올바르지 않습니다.",
    [ERROR_CODE.PLATFORM_SYNC_REQUEST_FAILED]: "공공 법령 Open API 호출에 실패했습니다.",
  };

  return codeMessages[code] ?? fallback;
}
