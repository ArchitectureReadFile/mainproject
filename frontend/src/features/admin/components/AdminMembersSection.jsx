import { updateAdminUser } from "@/api/admin";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { ERROR_CODE, getErrorMessageByCode } from "@/lib/errors";
import { useEffect, useState } from "react";

export default function AdminMembersSection({ users: initialUsers, total }) {
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("");
  const [users, setUsers] = useState(initialUsers);
  const [actionError, setActionError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [changeType, setChangeType] = useState("status");
  const [nextValue, setNextValue] = useState("active");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setUsers(initialUsers);
  }, [initialUsers]);

  useEffect(() => {
    if (!selectedUser) return;

    if (changeType === "status") {
      setNextValue(selectedUser.is_active ? "inactive" : "active");
      return;
    }

    setNextValue(selectedUser.plan === "PREMIUM" ? "FREE" : "PREMIUM");
  }, [changeType, selectedUser]);

  const filtered = users.filter((user) => {
    const matchSearch =
      !search || user.username.includes(search) || user.email.includes(search);
    const matchPlan = !planFilter || user.plan === planFilter;
    return matchSearch && matchPlan;
  });

  const openActionDialog = (user) => {
    setActionError(null);
    setSelectedUser(user);
    setChangeType("status");
    setNextValue(user.is_active ? "inactive" : "active");
    setDialogOpen(true);
  };

  const closeDialog = () => {
    if (isSubmitting) return;
    setDialogOpen(false);
    setSelectedUser(null);
    setActionError(null);
  };

  const handleSubmit = async () => {
    if (!selectedUser) return;

    setActionError(null);
    setIsSubmitting(true);

    const payload =
      changeType === "status"
        ? { is_active: nextValue === "active" }
        : { plan: nextValue };

    const optimisticUser = {
      ...selectedUser,
      ...(changeType === "status"
        ? { is_active: nextValue === "active" }
        : { plan: nextValue }),
    };

    setUsers((prev) =>
      prev.map((user) => (user.id === selectedUser.id ? optimisticUser : user))
    );

    try {
      const updated = await updateAdminUser(selectedUser.id, payload);
      setUsers((prev) =>
        prev.map((user) =>
          user.id === selectedUser.id
            ? {
                ...user,
                is_active: updated.is_active,
                plan: updated.plan,
              }
            : user
        )
      );
      setDialogOpen(false);
      setSelectedUser(null);
      setActionError(null);
    } catch (error) {
      setUsers((prev) =>
        prev.map((user) => (user.id === selectedUser.id ? selectedUser : user))
      );
      const message =
        error.code === ERROR_CODE.AUTH_FORBIDDEN
          ? "관리자 계정은 변경할 수 없습니다."
          : getErrorMessageByCode(
              error.code,
              error.message ?? "회원 변경에 실패했습니다."
            );
      setActionError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="이름 또는 이메일 검색"
          className="flex-1 rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
        />
        <select
          value={planFilter}
          onChange={(event) => setPlanFilter(event.target.value)}
          className="rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground"
        >
          <option value="">전체 플랜</option>
          <option value="FREE">FREE</option>
          <option value="PREMIUM">PREMIUM</option>
        </select>
      </div>

      {actionError && !dialogOpen && (
        <div className="rounded-xl border border-destructive/25 bg-destructive/10 px-4 py-2">
          <p className="text-sm text-destructive">{actionError}</p>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        전체 {total.toLocaleString()}명 / 필터 결과 {filtered.length}명
      </p>

      <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-muted/60 text-xs text-muted-foreground">
            <tr>
              <th className="px-4 py-3 text-left">이름</th>
              <th className="px-4 py-3 text-left">이메일</th>
              <th className="px-4 py-3 text-left">플랜</th>
              <th className="px-4 py-3 text-left">상태</th>
              <th className="px-4 py-3 text-center">활성 그룹 수</th>
              <th className="px-4 py-3 text-left">가입일</th>
              <th className="px-4 py-3 text-left">액션</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.map((user) => (
              <tr key={user.id} className="bg-card transition-colors hover:bg-accent/40">
                <td className="px-4 py-3 font-medium text-foreground">
                  {user.username}
                </td>
                <td className="px-4 py-3 text-muted-foreground">{user.email}</td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      user.plan === "PREMIUM"
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {user.plan}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      user.is_active
                        ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                        : "bg-destructive/10 text-destructive"
                    }`}
                  >
                    {user.is_active ? "활성" : "비활성"}
                  </span>
                </td>
                <td className="px-4 py-3 text-center text-foreground">{user.active_group_count}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  {user.created_at?.slice(0, 10)}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => openActionDialog(user)}
                    className="rounded-lg bg-secondary px-3 py-1 text-xs text-secondary-foreground transition-colors hover:bg-secondary/80"
                  >
                    변경
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={dialogOpen} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>회원 정보 변경</DialogTitle>
            <DialogDescription>
              {selectedUser
                ? `${selectedUser.username}의 상태 또는 플랜을 변경합니다.`
                : "변경할 항목을 선택해주세요."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                변경 항목
              </label>
              <select
                value={changeType}
                onChange={(event) => setChangeType(event.target.value)}
                className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground"
              >
                <option value="status">상태</option>
                <option value="plan">플랜</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                변경 값
              </label>
              <select
                value={nextValue}
                onChange={(event) => setNextValue(event.target.value)}
                className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground"
              >
                {changeType === "status" ? (
                  <>
                    <option value="active">활성</option>
                    <option value="inactive">비활성</option>
                  </>
                ) : (
                  <>
                    <option value="FREE">FREE</option>
                    <option value="PREMIUM">PREMIUM</option>
                  </>
                )}
              </select>
            </div>

            {actionError && (
              <div className="rounded-xl border border-destructive/25 bg-destructive/10 px-4 py-2">
                <p className="text-sm text-destructive">{actionError}</p>
              </div>
            )}
          </div>

          <DialogFooter>
            <button
              type="button"
              onClick={closeDialog}
              disabled={isSubmitting}
              className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent disabled:opacity-50"
            >
              취소
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              {isSubmitting ? "저장 중..." : "저장"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
