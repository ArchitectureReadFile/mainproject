import { updateAdminUserStatus } from "@/api/admin";
import { ERROR_CODE, getErrorMessageByCode } from "@/lib/errors";
import { useEffect, useState } from "react";

export default function AdminMembersSection({ users: initialUsers, total }) {
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("");
  const [users, setUsers] = useState(initialUsers);
  const [toggleError, setToggleError] = useState(null);

  useEffect(() => {
    setUsers(initialUsers);
  }, [initialUsers]);

  const filtered = users.filter((u) => {
    const matchSearch = !search || u.username.includes(search) || u.email.includes(search);
    const matchPlan = !planFilter || u.plan === planFilter;
    return matchSearch && matchPlan;
  });

  const handleStatusToggle = async (user) => {
    setToggleError(null);
    const nextActive = !user.is_active;

    // 낙관적 업데이트
    setUsers((prev) =>
      prev.map((u) => (u.id === user.id ? { ...u, is_active: nextActive } : u))
    );
    try {
      await updateAdminUserStatus(user.id, nextActive);
    } catch (e) {
      // 롤백
      setUsers((prev) =>
        prev.map((u) => (u.id === user.id ? { ...u, is_active: user.is_active } : u))
      );
      // ADMIN/self 차단(403) 등 알려진 에러는 메시지로 표시
      const msg =
        e.code === ERROR_CODE.AUTH_FORBIDDEN
          ? "관리자 계정은 변경할 수 없습니다."
          : getErrorMessageByCode(e.code, e.message ?? "상태 변경에 실패했습니다.");
      setToggleError(msg);
    }
  };

  return (
    <div className="space-y-4">
      {/* 필터 바 */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="이름 또는 이메일 검색"
          className="flex-1 border rounded-lg px-3 py-2 text-sm"
        />
        <select
          value={planFilter}
          onChange={(e) => setPlanFilter(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm"
        >
          <option value="">전체 플랜</option>
          <option value="FREE">FREE</option>
          <option value="PREMIUM">PREMIUM</option>
        </select>
      </div>

      {toggleError && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          <p className="text-sm text-red-600">{toggleError}</p>
        </div>
      )}

      <p className="text-xs text-gray-400">전체 {total.toLocaleString()}명 / 필터 결과 {filtered.length}명</p>

      {/* 테이블 */}
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
                <td className="px-4 py-3 font-medium text-gray-800">{user.username}</td>
                <td className="px-4 py-3 text-gray-500">{user.email}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    user.plan === "PREMIUM"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-gray-100 text-gray-500"
                  }`}>
                    {user.plan}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    user.is_active
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-500"
                  }`}>
                    {user.is_active ? "활성" : "비활성"}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">{user.active_group_count}</td>
                <td className="px-4 py-3 text-gray-400">{user.created_at?.slice(0, 10)}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleStatusToggle(user)}
                    className={`text-xs px-3 py-1 rounded-lg ${
                      user.is_active
                        ? "bg-red-50 text-red-600 hover:bg-red-100"
                        : "bg-green-50 text-green-600 hover:bg-green-100"
                    }`}
                  >
                    {user.is_active ? "비활성화" : "활성화"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
