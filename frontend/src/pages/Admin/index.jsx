import { fetchAdminPlatformSummary, fetchAdminStats, fetchAdminUsage, fetchAdminUsers } from "@/api/admin";
import AdminMembersSection from "@/features/admin/components/AdminMembersSection";
import AdminOverviewSection from "@/features/admin/components/AdminOverviewSection";
import AdminRagDbSection from "@/features/admin/components/AdminRagDbSection";
import AdminUsageSection from "@/features/admin/components/AdminUsageSection";
import { ERROR_CODE } from "@/lib/errors";
import { useCallback, useEffect, useState } from "react";

const TABS = [
  { key: "overview", label: "개요" },
  { key: "usage", label: "사용량" },
  { key: "ragdb", label: "RAG DB 관리" },
  { key: "members", label: "회원 관리" },
];

const FETCHER_MAP = {
  overview: fetchAdminStats,
  usage: fetchAdminUsage,
  ragdb: fetchAdminPlatformSummary,
  members: fetchAdminUsers,
};

const SETTER_MAP = (setters) => ({
  overview: setters.setStats,
  usage: setters.setUsage,
  ragdb: setters.setPlatformSummary,
  members: setters.setUsers,
});

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState("overview");
  const [stats, setStats] = useState(null);
  const [usage, setUsage] = useState(null);
  const [platformSummary, setPlatformSummary] = useState(null);
  const [users, setUsers] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [forbidden, setForbidden] = useState(false);

  const loadTab = useCallback((tab) => {
    const fetcher = FETCHER_MAP[tab];
    const setter = SETTER_MAP({ setStats, setUsage, setPlatformSummary, setUsers })[tab];
    if (!fetcher || !setter) return;

    setLoading(true);
    setError(null);
    fetcher()
      .then(setter)
      .catch((e) => {
        // 403 — ADMIN이 아닌 계정 접근 차단
        if (e.code === ERROR_CODE.AUTH_FORBIDDEN) {
          setForbidden(true);
          return;
        }
        setError(e.message ?? "데이터를 불러오지 못했습니다.");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadTab(activeTab);
  }, [activeTab, loadTab]);

  const handleRagRefetch = useCallback(() => loadTab("ragdb"), [loadTab]);

  // 권한 없는 경우 전체 페이지 차단
  if (forbidden) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="mt-20 text-center">
          <p className="text-2xl font-bold text-gray-700 mb-2">접근 권한이 없습니다</p>
          <p className="text-sm text-gray-400">관리자 계정으로 로그인해주세요.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">관리자 대시보드</h1>

      {/* 탭 */}
      <div className="flex gap-2 border-b mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && <p className="text-gray-400 text-sm">불러오는 중...</p>}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          {activeTab === "overview" && stats && <AdminOverviewSection stats={stats} />}
          {activeTab === "usage" && usage && <AdminUsageSection usage={usage} />}
          {activeTab === "ragdb" && platformSummary && (
            <AdminRagDbSection summary={platformSummary} onRefetch={handleRagRefetch} />
          )}
          {activeTab === "members" && (
            <AdminMembersSection users={users.items} total={users.total} />
          )}
        </>
      )}
    </div>
  );
}
