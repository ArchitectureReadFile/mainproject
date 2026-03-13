/**
 * 백엔드 errors/error_codes.py 와 1:1 대응되는 에러 코드 상수입니다.
 *
 * 사용 예시:
 *   import { ERROR_CODE } from "@/lib/errors";
 *   if (error.code === ERROR_CODE.AUTH_TOKEN_MISSING) { ... }
 */

export const ERROR_CODE = {
  // ── 인증 (AUTH) ────────────────────────────────────────────
  AUTH_TOKEN_MISSING:           "AUTH_001", // 액세스 토큰 없음 (로그인 필요)
  AUTH_TOKEN_INVALID:           "AUTH_002", // 액세스 토큰 유효하지 않음
  AUTH_REFRESH_TOKEN_MISSING:   "AUTH_003", // 리프레시 토큰 없음
  AUTH_REFRESH_TOKEN_EXPIRED:   "AUTH_004", // 리프레시 토큰 만료
  AUTH_REFRESH_TOKEN_INVALID:   "AUTH_005", // 리프레시 토큰 디코딩 실패
  AUTH_USER_INVALID:            "AUTH_006", // 유효하지 않은 사용자 상태
  AUTH_FORBIDDEN:               "AUTH_007", // 권한 없음

  // ── 사용자 (USER) ───────────────────────────────────────────
  USER_NOT_FOUND:               "USER_001", // 사용자를 찾을 수 없음
  USER_ACCOUNT_NOT_FOUND:       "USER_002", // 이메일로 가입된 계정 없음 (confirm-account)
  USER_INACTIVE:                "USER_003", // 비활성화된 계정
  USER_INVALID_CREDENTIALS:     "USER_004", // 이메일 또는 비밀번호 불일치
  USER_EMAIL_ALREADY_EXISTS:    "USER_005", // 이메일 중복
  USER_USERNAME_ALREADY_EXISTS: "USER_006", // 닉네임 중복
  USER_PASSWORD_TOO_LONG:       "USER_007", // 비밀번호 72바이트 초과
  USER_EMAIL_NOT_VERIFIED:      "USER_008", // 이메일 인증 미완료 또는 만료
  USER_RATE_LIMIT_EXCEEDED:     "USER_009", // 로그인 시도 횟수 초과

  // ── 이메일 (EMAIL) ──────────────────────────────────────────
  EMAIL_SEND_FAILED:            "EMAIL_001", // 이메일 발송 실패
  EMAIL_CODE_NOT_FOUND:         "EMAIL_002", // 인증 코드 만료 또는 없음
  EMAIL_CODE_MISMATCH:          "EMAIL_003", // 인증 코드 불일치

  // ── 문서 (DOC) ──────────────────────────────────────────────
  DOC_NOT_FOUND:                "DOC_001",  // 문서를 찾을 수 없음
  DOC_PDF_TEXT_TOO_SHORT:       "DOC_002",  // PDF 텍스트 추출 불충분 (스캔본)
  DOC_PDF_PARSE_FAILED:         "DOC_003",  // PDF 파일 읽기 실패
  DOC_INVALID_FILE_TYPE:        "DOC_004",  // PDF 이외 업로드
  DOC_FILE_TOO_LARGE:           "DOC_005",  // 파일 크기 초과

  // ── LLM 요약 (LLM) ─────────────────────────────────────────
  LLM_EMPTY_PAGES:              "LLM_001",  // 텍스트 추출 결과 없음
  LLM_ALL_PROFILES_FAILED:      "LLM_002",  // Ollama 모든 프로파일 실패

  // ── 요약 결과 (SUM) ─────────────────────────────────────────
  SUM_NOT_FOUND:                "SUM_001",  // 요약 결과를 찾을 수 없음

  // ── 파일 다운로드 (FILE) ────────────────────────────────────
  FILE_NOT_FOUND:               "FILE_001", // 파일을 찾을 수 없음
};

/**
 * Axios 응답 에러에서 백엔드 에러 코드를 추출합니다.
 *
 * 사용 예시:
 *   const code = getErrorCode(error);
 *   if (code === ERROR_CODE.USER_EMAIL_ALREADY_EXISTS) { ... }
 */
export function getErrorCode(error) {
  return error.response?.data?.code ?? null;
}

/**
 * Axios 응답 에러에서 백엔드 에러 메시지를 추출합니다.
 */
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
    [ERROR_CODE.DOC_INVALID_FILE_TYPE]: "PDF 파일만 업로드 가능합니다.",
    [ERROR_CODE.DOC_FILE_TOO_LARGE]: "파일 크기는 20MB 이하여야 합니다.",
  };

  return codeMessages[code] ?? fallback;
}
