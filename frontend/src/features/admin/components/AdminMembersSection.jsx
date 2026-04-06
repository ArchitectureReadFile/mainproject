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
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
        />
        <select
          value={planFilter}
          onChange={(event) => setPlanFilter(event.target.value)}
          className="border rounded-lg px-3 py-2 text-sm"
        >
          <option value="">전체 플랜</option>
          <option value="FREE">FREE</option>
          <option value="PREMIUM">PREMIUM</option>
        </select>
      </div>

      {actionError && !dialogOpen && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          <p className="text-sm text-red-600">{actionError}</p>
        </div>
      )}

      <p className="text-xs text-gray-400">
        전체 {total.toLocaleString()}명 / 필터 결과 {filtered.length}명
      </p>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm border rounded-xl overflow-hidden">
          <thead className="bg-gray-50 text-gray-500 text-xs">
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
          <tbody className="divide-y">
            {filtered.map((user) => (
              <tr key={user.id} className="bg-white hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-800">
                  {user.username}
                </td>
                <td className="px-4 py-3 text-gray-500">{user.email}</td>
                <td className="px-4 py-3">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      user.plan === "PREMIUM"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {user.plan}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      user.is_active
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-500"
                    }`}
                  >
                    {user.is_active ? "활성" : "비활성"}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">{user.active_group_count}</td>
                <td className="px-4 py-3 text-gray-400">
                  {user.created_at?.slice(0, 10)}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => openActionDialog(user)}
                    className="text-xs px-3 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200"
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
              <label className="text-sm font-medium text-gray-700">
                변경 항목
              </label>
              <select
                value={changeType}
                onChange={(event) => setChangeType(event.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm"
              >
                <option value="status">상태</option>
                <option value="plan">플랜</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">
                변경 값
              </label>
              <select
                value={nextValue}
                onChange={(event) => setNextValue(event.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm"
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
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2">
                <p className="text-sm text-red-600">{actionError}</p>
              </div>
            )}
          </div>

          <DialogFooter>
            <button
              type="button"
              onClick={closeDialog}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50"
            >
              취소
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {isSubmitting ? "저장 중..." : "저장"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
