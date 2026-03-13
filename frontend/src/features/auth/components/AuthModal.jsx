import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import styles from "./AuthModal.module.css";
import ConfirmAccountForm from "./forms/ConfirmAccountForm.jsx";
import LoginSignupForm from "./forms/LoginSignupForm.jsx";
import ResetPasswordForm from "./forms/ResetPasswordForm.jsx";

export default function AuthModal({ mode, open, onClose }) {
  const [view, setView] = useState(mode);
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!open) {
      setView(mode);
      return;
    }
    setView(mode);
  }, [open, mode]);

  useEffect(() => {
    if (!open) return;

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
    };

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className={styles.overlay}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}>
      <section
        ref={dialogRef}
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-title">
        <div className={styles.header}>
          <h2 id="auth-modal-title" className={styles.title}>
            {view === "login" && "로그인"}
            {view === "signup" && "회원가입"}
            {view === "confirmAccount" && "가입 정보 확인"}
            {view === "resetPassword" && "비밀번호 재설정"}
          </h2>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}>
            <X size={24} />
          </button>
        </div>

        <div className={styles.content}>
          {(view === "login" || view === "signup") && (
            <LoginSignupForm view={view} setView={setView} onClose={onClose} />
          )}

          {view === "confirmAccount" && <ConfirmAccountForm setView={setView} />}

          {view === "resetPassword" && <ResetPasswordForm setView={setView} />}
        </div>
      </section>
    </div>
  );
}
