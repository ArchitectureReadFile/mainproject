import axios from "axios";
import { getAccessToken } from "../features/auth/utils/authCookie";
import { ERROR_CODE } from "./errors";

const axiosInstance = axios.create({
  baseURL: `/api`,
  withCredentials: true,
});

// 요청 인터셉터: Access Token 자동 헤더 추가
axiosInstance.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * 응답 에러에서 백엔드 에러 코드를 추출합니다.
 * AppException 형식: { code: "AUTH_001", message: "..." }
 */
const extractErrorCode = (error) => {
  return error.response?.data?.code ?? null;
};

/**
 * 응답 에러에서 표시할 메시지를 추출합니다.
 * 우선순위: AppException message → FastAPI detail → fallback
 */
const parseAxiosError = (error, fallback) => {
  const payload = error.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  // AppException 형식
  if (typeof payload.message === "string") return payload.message;
  // FastAPI validation 에러 형식
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    const messages = payload.detail
      .map((item) => (typeof item === "string" ? item : item?.msg))
      .filter(Boolean);
    if (messages.length > 0) return messages.join(" / ");
  }
  return fallback;
};

/**
 * 리프레시 토큰으로 액세스 토큰 재발급을 시도합니다.
 * 실패 시 로그인 페이지로 이동합니다.
 */
const tryRefreshToken = async (originalRequest) => {
  originalRequest._retry = true;
  try {
    await axios.post(`/api/auth/refresh`, {}, { withCredentials: true });
    return axiosInstance(originalRequest);
  } catch {
    window.location.href = "/";
    return Promise.reject(new Error("세션이 만료되었습니다. 다시 로그인해주세요."));
  }
};

axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const code = extractErrorCode(error);
    const isAuthEndpoint =
      originalRequest.url.includes("/auth/login") ||
      originalRequest.url.includes("/auth/refresh") ||
      originalRequest.url.includes("/auth/me");

    // 액세스 토큰 만료/무효 → refresh 시도 (auth 엔드포인트 제외, 재시도 1회 제한)
    if (
      !originalRequest._retry &&
      !isAuthEndpoint &&
      (code === ERROR_CODE.AUTH_TOKEN_MISSING || code === ERROR_CODE.AUTH_TOKEN_INVALID)
    ) {
      return tryRefreshToken(originalRequest);
    }

    // 리프레시 토큰 만료/무효 → 로그인 페이지로
    if (
      code === ERROR_CODE.AUTH_REFRESH_TOKEN_EXPIRED ||
      code === ERROR_CODE.AUTH_REFRESH_TOKEN_INVALID ||
      code === ERROR_CODE.AUTH_REFRESH_TOKEN_MISSING
    ) {
      window.location.href = "/";
      return Promise.reject(new Error("세션이 만료되었습니다. 다시 로그인해주세요."));
    }

    const fallback = originalRequest.url.includes("/auth/login")
      ? "로그인에 실패했습니다."
      : "요청에 실패했습니다.";

    const message = parseAxiosError(error, fallback);
    const err = new Error(message);
    err.code = code; // 컴포넌트에서 code 기반 분기가 필요할 때 사용
    return Promise.reject(err);
  },
);

export default axiosInstance;
