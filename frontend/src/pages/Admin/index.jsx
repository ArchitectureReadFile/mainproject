import { fetchAdminPlatformSummary, fetchAdminStats, fetchAdminUsage, fetchAdminUsers } from "@/api/admin";
import AdminMembersSection from "@/features/admin/components/AdminMembersSection";
import AdminDocumentAiSection from "@/features/admin/components/AdminDocumentAiSection";
import AdminOverviewSection from "@/features/admin/components/AdminOverviewSection";
import AdminRagDbSection from "@/features/admin/components/AdminRagDbSection";
import { ERROR_CODE } from "@/lib/errors";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

const TABS = [
  { key: "overview", label: "개요" },
  { key: "documentAi", label: "문서/AI 현황" },
  { key: "ragdb", label: "RAG DB 관리" },
  { key: "members", label: "회원 관리" },
];

const FETCHER_MAP = {
  overview: fetchAdminStats,
  documentAi: fetchAdminUsage,
  ragdb: fetchAdminPlatformSummary,
  members: fetchAdminUsers,
};

const SETTER_MAP = (setters) => ({
  overview: setters.setStats,
  documentAi: setters.setUsage,
  ragdb: setters.setPlatformSummary,
  members: setters.setUsers,
});

export default function AdminPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get("tab");
  const [activeTab, setActiveTab] = useState(() =>
    TABS.some((tab) => tab.key === tabFromUrl) ? tabFromUrl : "overview",
  );
  const [stats, setStats] = useState(null);
  const [usage, setUsage] = useState(null);
  const [platformSummary, setPlatformSummary] = useState(null);
  const [users, setUsers] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    const nextTab = TABS.some((tab) => tab.key === tabFromUrl) ? tabFromUrl : "overview";
    setActiveTab(nextTab);
  }, [tabFromUrl]);

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

  const handleTabChange = useCallback((tab) => {
    setActiveTab(tab);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("tab", tab);
    setSearchParams(nextParams);
  }, [searchParams, setSearchParams]);

  const handleRagRefetch = useCallback(() => loadTab("ragdb"), [loadTab]);

  // 권한 없는 경우 전체 페이지 차단
  if (forbidden) {
    return (
      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="mt-20 text-center">
          <p className="mb-2 text-2xl font-bold text-foreground">접근 권한이 없습니다</p>
          <p className="text-sm text-muted-foreground">관리자 계정으로 로그인해주세요.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">관리자 대시보드</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          사용자, 문서 처리, 플랫폼 데이터를 한 곳에서 확인하고 운영합니다.
        </p>
      </div>

      <div className="mb-6 flex flex-wrap gap-2 border-b border-border pb-2">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleTabChange(tab.key)}
            className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-muted-foreground">불러오는 중...</p>}
      {error && (
        <div className="rounded-xl border border-destructive/25 bg-destructive/10 px-4 py-3">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          {activeTab === "overview" && stats && <AdminOverviewSection stats={stats} />}
          {activeTab === "documentAi" && usage && <AdminDocumentAiSection usage={usage} />}
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
