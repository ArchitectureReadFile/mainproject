import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { getErrorMessageByCode } from "../../../../lib/errors";
import { confirmAccount } from "../../api/authApi";
import { sendVerificationCode, verifyCode } from "../../api/emailApi";
import styles from "./ConfirmAccountForm.module.css";

export default function ConfirmAccountForm({ setView }) {
  const [findEmail, setFindEmail] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [result, setResult] = useState(null);

  const [isCodeSent, setIsCodeSent] = useState(false);
  const [isVerified, setIsVerified] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const onSendCode = async () => {
    setError("");
    const cleanEmail = findEmail.trim().toLowerCase();
    if (!cleanEmail) {
      setError("이메일을 입력해주세요.");
      return;
    }
    setLoading(true);
    try {
      await sendVerificationCode(cleanEmail);
      setIsCodeSent(true);
      toast.success("인증번호가 발송되었습니다.");
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || "발송에 실패했습니다."));
    } finally {
      setLoading(false);
    }
  };

  const onVerifyCode = async () => {
    setError("");
    const cleanEmail = findEmail.trim().toLowerCase();
    const cleanCode = verificationCode.trim();

    if (!cleanEmail || !cleanCode) {
      setError("이메일과 인증번호를 모두 확인해주세요.");
      return;
    }

    setLoading(true);
    try {
      await verifyCode(cleanEmail, cleanCode);
      const res = await confirmAccount(cleanEmail);
      setResult(res);
      setIsVerified(true);
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || "인증번호가 일치하지 않거나 만료되었습니다."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.form}>
      {!isVerified ? (
        <>
          <div className={styles.field}>
            <label htmlFor="find-email">가입한 이메일 주소</label>
            <div className={styles.inputGroup}>
              <input
                id="find-email"
                ref={inputRef}
                type="email"
                value={findEmail}
                onChange={(e) => setFindEmail(e.target.value)}
                disabled={loading}
                placeholder="example@email.com"
              />
              <button
                type="button"
                onClick={onSendCode}
                disabled={loading || !findEmail.trim()}
                className={styles.actionButton}
              >
                {isCodeSent ? "재발송" : "번호발송"}
              </button>
            </div>
          </div>

          {isCodeSent && (
            <div className={styles.field}>
              <label htmlFor="verification-code">인증번호 확인</label>
              <div className={styles.inputGroup}>
                <input
                  id="verification-code"
                  type="text"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  disabled={loading}
                  placeholder="6자리 숫자 입력"
                />
                <button
                  type="button"
                  onClick={onVerifyCode}
                  disabled={loading || !verificationCode.trim()}
                  className={styles.actionButton}
                >
                  확인
                </button>
              </div>
            </div>
          )}

          {error && <p className={styles.error}>{error}</p>}

          <div className={styles.infoText}>
            이메일 인증 후 가입 여부를 확인할 수 있습니다.
          </div>

          <div className={styles.footer}>
            <button
              type="button"
              className={styles.textButton}
              onClick={() => setView("login")}
              disabled={loading}
            >
              돌아가기
            </button>
          </div>
        </>
      ) : (
        <div className={styles.resultContainer}>
          <div className={styles.resultBox}>
            <p className={styles.successMsg}>가입된 계정 정보를 찾았습니다!</p>
            <div className={styles.resultItem}>
              <span className={styles.resultLabel}>로그인 계정</span>
              <span className={styles.resultValue}>{result.email}</span>
            </div>
            <div className={styles.resultItem}>
              <span className={styles.resultLabel}>닉네임</span>
              <span className={styles.resultValue}>{result.username}</span>
            </div>
          </div>

          <button
            type="button"
            className={styles.primaryButton}
            onClick={() => setView("login")}
          >
            로그인하러 가기
          </button>
        </div>
      )}
    </div>
  );
}
