import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { Label } from '@/shared/ui/label';
import { AlertCircle, ChevronLeft, Mail, ShieldCheck, UserCheck, CheckCircle2 } from 'lucide-react';
import { useEffect, useRef, useState } from "react";
import { getErrorMessageByCode } from "@/shared/lib/errors";
import { confirmAccount } from "../../api/authApi";
import { sendVerificationCode, verifyCode } from "../../api/emailApi";

const EMAIL_VERIFY_INIT = {
  codeSent: false, code: '', verified: false,
  sending: false, verifying: false, error: '', success: '',
};

export default function ConfirmAccountForm({ setView }) {
  const [findEmail, setFindEmail] = useState("");
  const [result, setResult] = useState(null);
  const [emailVerify, setEmailVerify] = useState(EMAIL_VERIFY_INIT);
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
    setEmailVerify((prev) => ({ ...prev, sending: true, error: '', success: '' }));
    try {
      await sendVerificationCode(cleanEmail);
      setEmailVerify((prev) => ({ ...prev, codeSent: true, sending: false, success: '인증번호가 발송되었습니다.' }));
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || "발송에 실패했습니다."));
      setEmailVerify((prev) => ({ ...prev, sending: false }));
    }
  };

  const onVerifyCode = async () => {
    setError("");
    const cleanEmail = findEmail.trim().toLowerCase();
    const cleanCode = emailVerify.code.trim();

    if (!cleanEmail || !cleanCode) {
      setError("이메일과 인증번호를 모두 확인해주세요.");
      return;
    }

    setLoading(true);
    setEmailVerify((prev) => ({ ...prev, verifying: true }));
    try {
      await verifyCode(cleanEmail, cleanCode);
      const res = await confirmAccount(cleanEmail);
      setResult(res);
      setEmailVerify((prev) => ({ ...prev, verifying: false, verified: true }));
    } catch (err) {
      setError(getErrorMessageByCode(err.code, err.message || "인증번호가 일치하지 않거나 만료되었습니다."));
      setEmailVerify((prev) => ({ ...prev, verifying: false }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 py-0.5">
      {!emailVerify.verified ? (
        <>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="find-email" className="text-[12px] font-semibold text-muted-foreground ml-1">이메일 주소</Label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
                  <Input
                    id="find-email"
                    ref={inputRef}
                    type="email"
                    className="pl-9 h-11 bg-muted/5 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-indigo-500/30 shadow-none text-foreground"
                    value={findEmail}
                    onChange={(e) => {
                      setFindEmail(e.target.value);
                      setEmailVerify(EMAIL_VERIFY_INIT);
                    }}
                    disabled={loading || emailVerify.sending}
                    placeholder="example@email.com"
                  />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onSendCode}
                  disabled={emailVerify.sending || emailVerify.verified || !findEmail.trim()}
                  className="shrink-0 h-11 px-4 font-bold border-muted-foreground/40 bg-muted/5 hover:bg-muted/10 text-muted-foreground transition-all duration-300"
                >
                  {emailVerify.verified ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : emailVerify.sending ? (
                    <span className="animate-pulse">...</span>
                  ) : emailVerify.codeSent ? (
                    '재발송'
                  ) : (
                    '인증요청'
                  )}
                </Button>
              </div>
            </div>

            {emailVerify.codeSent && (
              <div className="flex flex-col gap-1.5 animate-in fade-in slide-in-from-top-2 duration-300">
                <Label htmlFor="verification-code" className="text-[12px] font-semibold text-muted-foreground ml-1">인증번호</Label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/60" />
                    <Input
                      id="verification-code"
                      type="text"
                      className="pl-9 h-11 bg-muted/5 focus-visible:ring-0 focus-visible:ring-offset-0 focus:border-indigo-500/30 shadow-none text-foreground font-medium"
                      value={emailVerify.code}
                      onChange={(e) => setEmailVerify((prev) => ({ ...prev, code: e.target.value, error: '' }))}
                      disabled={loading || emailVerify.verifying}
                      placeholder="6자리 숫자"
                      maxLength={6}
                    />
                  </div>
                  <Button
                    type="button"
                    onClick={onVerifyCode}
                    disabled={loading || !emailVerify.code.trim()}
                    className="shrink-0 h-11 px-6 font-bold bg-indigo-500/75 hover:bg-indigo-500/85 dark:bg-indigo-600/60 dark:hover:bg-indigo-600/70 text-white shadow-none transition-all duration-300"
                  >
                    {emailVerify.verifying ? <span className="animate-pulse">...</span> : "확인"}
                  </Button>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="bg-destructive/10 p-2.5 rounded-lg flex items-start gap-2 animate-in slide-in-from-top-1 duration-200">
              <AlertCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
              <p className="text-[13px] font-bold text-destructive leading-tight">{error}</p>
            </div>
          )}

          <div className="pt-6 border-t border-muted/40">
            <Button
              type="button"
              variant="ghost"
              className="w-full text-muted-foreground/70 hover:text-foreground gap-2 h-10 text-[13px] font-bold transition-all duration-300"
              onClick={() => setView("login")}
              disabled={loading}
            >
              <ChevronLeft className="w-4 h-4" />
              로그인으로 돌아가기
            </Button>
          </div>
        </>
      ) : (
        <div className="flex flex-col gap-6 animate-in zoom-in-95 duration-300">
          <div className="rounded-2xl border border-muted/40 bg-muted/5 p-8 text-card-foreground shadow-sm flex flex-col items-center text-center gap-4">
            <div className="w-16 h-16 rounded-full bg-emerald-50/50 dark:bg-emerald-900/10 flex items-center justify-center mb-1">
              <UserCheck className="w-8 h-8 text-emerald-600/60 dark:text-emerald-500/60" />
            </div>
            
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-foreground/80">계정 정보를 찾았습니다</h3>
              <p className="text-[13px] text-muted-foreground/70 font-medium">아래 정보로 다시 서비스를 이용해 보세요.</p>
            </div>

            <div className="w-full space-y-3 mt-4 pt-4 border-t border-muted/30">
              <div className="flex justify-between items-center py-0.5">
                <span className="text-[13px] font-bold text-muted-foreground/60">이메일</span>
                <span className="text-sm font-black text-foreground/90">{result?.email}</span>
              </div>
              <div className="flex justify-between items-center py-0.5">
                <span className="text-[13px] font-bold text-muted-foreground/60">사용자 이름</span>
                <span className="text-sm font-black text-foreground/90">{result?.username}</span>
              </div>
            </div>
          </div>

          <Button
            type="button"
            className="w-full h-12 text-base font-black bg-indigo-500/80 hover:bg-indigo-500/90 text-white shadow-none rounded-xl transition-all duration-300"
            onClick={() => setView("login")}
          >
            지금 로그인하기
          </Button>
        </div>
      )}
    </div>
  );
}
