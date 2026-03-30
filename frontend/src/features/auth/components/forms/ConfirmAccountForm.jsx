import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { getErrorMessageByCode } from "../../../../lib/errors";
import { confirmAccount } from "../../api/authApi";
import { sendVerificationCode, verifyCode } from "../../api/emailApi";

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
      toast.success("계정 정보 조회가 완료되었습니다.");
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || "인증번호가 일치하지 않거나 만료되었습니다."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {!isVerified ? (
        <>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="find-email">가입한 이메일 주소</Label>
            <div className="flex gap-2">
              <Input
                id="find-email"
                ref={inputRef}
                type="email"
                value={findEmail}
                onChange={(e) => setFindEmail(e.target.value)}
                disabled={loading}
                placeholder="example@email.com"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onSendCode}
                disabled={loading || !findEmail.trim()}
                className="shrink-0"
              >
                {isCodeSent ? "재발송" : "번호발송"}
              </Button>
            </div>
          </div>

          {isCodeSent && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="verification-code">인증번호 확인</Label>
              <div className="flex gap-2">
                <Input
                  id="verification-code"
                  type="text"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  disabled={loading}
                  placeholder="6자리 숫자 입력"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onVerifyCode}
                  disabled={loading || !verificationCode.trim()}
                  className="shrink-0"
                >
                  확인
                </Button>
              </div>
            </div>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          <p className="text-xs text-muted-foreground">
            이메일 인증 후 가입 여부를 확인할 수 있습니다.
          </p>

          <Button
            type="button"
            variant="ghost"
            className="w-full text-muted-foreground"
            onClick={() => setView("login")}
            disabled={loading}
          >
            로그인으로 돌아가기
          </Button>
        </>
      ) : (
        <div className="flex flex-col gap-6">
          <div className="rounded-lg border bg-card p-6 text-card-foreground shadow-sm">
            <h3 className="mb-4 text-center font-semibold text-primary">가입된 계정 정보를 찾았습니다!</h3>
            <div className="space-y-3">
              <div className="flex justify-between border-b pb-2">
                <span className="text-sm font-medium text-muted-foreground">로그인 계정</span>
                <span className="text-sm font-bold">{result?.email}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-sm font-medium text-muted-foreground">닉네임</span>
                <span className="text-sm font-bold">{result?.username}</span>
              </div>
            </div>
          </div>

          <Button
            type="button"
            className="w-full"
            onClick={() => setView("login")}
          >
            로그인하러 가기
          </Button>
        </div>
      )}
    </div>
  );
}
