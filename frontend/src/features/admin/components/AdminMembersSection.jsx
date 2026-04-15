import { updateAdminUser } from "@/shared/api/admin";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/Dialog";
import { ERROR_CODE, getErrorMessageByCode } from "@/shared/lib/errors";
import { BadgeCheck, Search, ShieldCheck, Sparkles, UserRoundX, Users } from "lucide-react";
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
  const [successMessage, setSuccessMessage] = useState(null);

  useEffect(() => {
    setUsers(initialUsers);
  }, [initialUsers]);

  useEffect(() => {
    if (!successMessage) return undefined;
    const timer = window.setTimeout(() => setSuccessMessage(null), 3000);
    return () => window.clearTimeout(timer);
  }, [successMessage]);

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
      !search ||
      user.username.toLowerCase().includes(search.toLowerCase()) ||
      user.email.toLowerCase().includes(search.toLowerCase());
    const matchPlan = !planFilter || user.plan === planFilter;
    return matchSearch && matchPlan;
  });
  const activeCount = filtered.filter((user) => user.is_active).length;
  const premiumCount = filtered.filter((user) => user.plan === "PREMIUM").length;
  const inactiveCount = filtered.filter((user) => !user.is_active).length;

  const openActionDialog = (user) => {
    setActionError(null);
    setSuccessMessage(null);
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
      setSuccessMessage(
        changeType === "status"
          ? `${updated.username} 사용자를 ${updated.is_active ? "활성" : "비활성"} 상태로 변경했습니다.`
          : `${updated.username} 사용자의 플랜을 ${updated.plan}으로 변경했습니다.`,
      );
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

  const resetFilters = () => {
    setSearch("");
    setPlanFilter("");
  };

  return (
    <div className="space-y-5">
      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={Users}
          label="조회 대상 회원"
          value={filtered.length.toLocaleString()}
          hint={`전체 ${total.toLocaleString()}명 중 현재 필터 결과`}
          tone="sky"
        />
        <MetricCard
          icon={ShieldCheck}
          label="활성 회원"
          value={activeCount.toLocaleString()}
          hint="현재 로그인 및 서비스 이용 가능"
          tone="emerald"
        />
        <MetricCard
          icon={Sparkles}
          label="PREMIUM 회원"
          value={premiumCount.toLocaleString()}
          hint="유료 플랜 적용 대상"
          tone="violet"
        />
        <MetricCard
          icon={UserRoundX}
          label="비활성 회원"
          value={inactiveCount.toLocaleString()}
          hint="상태 점검이 필요한 계정"
          tone="rose"
        />
      </section>

      <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-card-foreground">회원 검색 및 필터</p>
            <p className="mt-1 text-xs text-muted-foreground">
              이름 또는 이메일로 대상을 찾고, 플랜별로 빠르게 범위를 좁힐 수 있습니다.
            </p>
          </div>
          <div className="text-xs text-muted-foreground">
            전체 {total.toLocaleString()}명 / 필터 결과 {filtered.length.toLocaleString()}명
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-3 lg:flex-row">
          <label className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="이름 또는 이메일 검색"
              className="w-full rounded-xl border border-border bg-background py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground"
            />
          </label>
          <select
            value={planFilter}
            onChange={(event) => setPlanFilter(event.target.value)}
            className="rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">전체 플랜</option>
            <option value="FREE">FREE</option>
            <option value="PREMIUM">PREMIUM</option>
          </select>
          <button
            type="button"
            onClick={resetFilters}
            className="rounded-xl border border-border bg-background px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            필터 초기화
          </button>
        </div>
      </section>

      {actionError && !dialogOpen && (
        <div className="rounded-xl border border-destructive/25 bg-destructive/10 px-4 py-2">
          <p className="text-sm text-destructive">{actionError}</p>
        </div>
      )}

      {successMessage && (
        <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-2">
          <p className="text-sm text-emerald-700 dark:text-emerald-300">{successMessage}</p>
        </div>
      )}

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
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center">
                  <div className="mx-auto flex max-w-sm flex-col items-center gap-2">
                    <div className="rounded-full bg-muted p-3">
                      <Search className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <p className="text-sm font-medium text-foreground">조건에 맞는 회원이 없습니다</p>
                    <p className="text-xs text-muted-foreground">
                      검색어 또는 플랜 필터를 조정해 다시 확인해보세요.
                    </p>
                  </div>
                </td>
              </tr>
            )}
            {filtered.map((user) => (
              <tr key={user.id} className="bg-card transition-colors hover:bg-accent/40">
                <td className="px-4 py-3 font-medium text-foreground">
                  <div>
                    <p className="font-medium text-foreground">{user.username}</p>
                    <p className="mt-1 text-xs text-muted-foreground">ID {user.id}</p>
                  </div>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{user.email}</td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      user.plan === "PREMIUM"
                        ? "border border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300"
                        : "border border-slate-200 bg-slate-100 text-slate-700 dark:border-slate-500/30 dark:bg-slate-500/10 dark:text-slate-300"
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
                    className="inline-flex items-center gap-1 rounded-lg bg-secondary px-3 py-1.5 text-xs text-secondary-foreground transition-colors hover:bg-secondary/80"
                  >
                    <BadgeCheck className="h-3.5 w-3.5" />
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

function MetricCard({ icon: Icon, label, value, hint, tone = "sky" }) {
  const toneClasses = {
    sky: "bg-sky-50 text-sky-700 ring-sky-100 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/20",
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
    violet: "bg-violet-50 text-violet-700 ring-violet-100 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/20",
    rose: "bg-rose-50 text-rose-700 ring-rose-100 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/20",
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-foreground">{value}</p>
          <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
        </div>
        <div className={`rounded-2xl p-3 ring-1 ${toneClasses[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}
