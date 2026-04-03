import { fetchAdminPlatformFailures, stopAdminPlatform, syncAdminPlatform } from "@/api/admin";
import { ERROR_CODE, getErrorMessageByCode } from "@/lib/errors";
import { useEffect, useMemo, useState } from "react";

const SOURCE_OPTIONS = [
  { value: "law", label: "현행 법령" },
  { value: "precedent", label: "판례" },
  { value: "interpretation", label: "법령해석례" },
  { value: "admin_rule", label: "행정규칙" },
];

const _RUNNING_STATUSES = new Set(["queued", "running"]);

export default function AdminRagDbSection({ summary, onRefetch }) {
  const [actionError, setActionError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [activeSourceType, setActiveSourceType] = useState(null);
  const [failures, setFailures] = useState([]);
  const [failuresLoading, setFailuresLoading] = useState(false);

  const sourceMap = useMemo(
    () => Object.fromEntries(summary.sources.map((item) => [item.source_type, item])),
    [summary.sources],
  );

  useEffect(() => {
    setFailuresLoading(true);
    fetchAdminPlatformFailures({ limit: 20 })
      .then((data) => setFailures(data.items ?? []))
      .catch(() => setFailures([]))
      .finally(() => setFailuresLoading(false));
  }, [summary]);

  const withAction = async (fn, sourceType) => {
    setActionError(null);
    setActionLoading(true);
    setActiveSourceType(sourceType);
    try {
      const result = await fn();
      setLastSync(result);
      onRefetch();
    } catch (e) {
      const knownCodes = [
        ERROR_CODE.PLATFORM_SYNC_CONFIG_MISSING,
        ERROR_CODE.PLATFORM_SYNC_REQUEST_FAILED,
      ];
      if (knownCodes.includes(e.code)) {
        setActionError(getErrorMessageByCode(e.code));
      } else {
        setActionError(e.message ?? "요청에 실패했습니다.");
      }
    } finally {
      setActionLoading(false);
      setActiveSourceType(null);
    }
  };

  const handleSync = (sourceType) => {
    withAction(() => syncAdminPlatform({ source_type: sourceType }), sourceType);
  };

  const handleStop = (sourceType) => {
    withAction(() => stopAdminPlatform({ source_type: sourceType }), sourceType);
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
        <SummaryCard label="전체 문서" value={summary.total_documents.toLocaleString()} />
        <SummaryCard label="전체 청크" value={summary.total_chunks.toLocaleString()} />
        {SOURCE_OPTIONS.map((option) => (
          <SummaryCard
            key={option.value}
            label={option.label}
            value={(sourceMap[option.value]?.document_count ?? 0).toLocaleString()}
          />
        ))}
      </div>

      <div className="bg-white border rounded-xl p-4 shadow-sm space-y-4">
        <div>
          <p className="text-sm font-semibold text-gray-700">공공 데이터 전체 최신화</p>
          <p className="text-xs text-gray-400 mt-1">
            source별 전체 목록을 서버가 자동으로 순회해 신규 문서를 적재합니다. 작업 상태는 새로고침 시 반영됩니다.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {SOURCE_OPTIONS.map((option) => {
            const source = sourceMap[option.value];
            const isRunning = _RUNNING_STATUSES.has(source?.last_sync_status);
            const isThisLoading = actionLoading && activeSourceType === option.value;

            return (
              <div key={option.value} className="border rounded-lg p-4 flex flex-col gap-3">
                <div>
                  <p className="text-sm font-medium text-gray-800">{option.label}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    현재 문서 {source?.document_count ?? 0} / 청크{" "}
                    {source?.chunk_count ?? 0}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {describeSourceState(source)}
                  </p>
                </div>
                {isRunning ? (
                  <button
                    onClick={() => handleStop(option.value)}
                    disabled={isThisLoading}
                    className="px-4 py-2 bg-red-500 text-white text-sm rounded-lg hover:bg-red-600 disabled:opacity-50"
                  >
                    {isThisLoading ? "처리 중..." : "정지"}
                  </button>
                ) : (
                  <button
                    onClick={() => handleSync(option.value)}
                    disabled={actionLoading}
                    className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {isThisLoading ? "최신화 중..." : "전체 최신화"}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {actionError && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2">
            <p className="text-sm text-red-600">{actionError}</p>
          </div>
        )}

        {lastSync && (
          <div className="bg-gray-50 border rounded-lg px-4 py-3 space-y-2">
            <div className="flex flex-wrap gap-4 text-sm">
              <span>상태 {syncStatusLabel(lastSync.status)}</span>
              {"fetched" in lastSync && <span>조회 {lastSync.fetched}건</span>}
              {"created" in lastSync && <span className="text-green-700">생성 {lastSync.created}건</span>}
              {"skipped" in lastSync && <span className="text-gray-600">스킵 {lastSync.skipped}건</span>}
              {"failed" in lastSync && <span className="text-red-600">실패 {lastSync.failed}건</span>}
            </div>
            <div className="text-xs text-gray-500">{lastSync.message}</div>
            {lastSync.status !== "cancelled" && (
              <div className="text-xs text-gray-400">
                작업이 백그라운드에서 계속 진행됩니다. 새로고침하면 현재 페이지와 마지막 처리 문서를 확인할 수 있습니다.
              </div>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel title="source별 현황">
          {summary.sources.map((item) => (
            <div key={item.source_type} className="flex justify-between items-center py-2 border-b text-sm">
              <div>
                <p className="text-gray-700">{item.label}</p>
                <p className="text-xs text-gray-400">문서 {item.document_count} / 청크 {item.chunk_count}</p>
                <p className="text-xs text-gray-400">
                  {formatLastRunLabel(item)}
                </p>
                {item.last_sync_status && (
                  <p className="text-xs text-gray-400">
                    현재 상태 {syncStatusLabel(item.last_sync_status)}
                    {formatProgressSummary(item)}
                  </p>
                )}
                {(item.last_display_title || item.last_external_id) && (
                  <p className="text-xs text-gray-400 truncate" title={item.last_display_title ?? item.last_external_id}>
                    마지막 확인 {item.last_display_title ?? item.last_external_id}
                  </p>
                )}
                {item.last_sync_message && <p className="text-xs text-gray-500">{item.last_sync_message}</p>}
              </div>
            </div>
          ))}
        </Panel>

        <Panel title="최근 적재 문서">
          {summary.recent_items.length === 0 && <EmptyRow />}
          {summary.recent_items.map((item) => (
            <div key={`${item.source_type}-${item.external_id}`} className="py-2 border-b text-sm">
              <p className="text-gray-700 truncate" title={item.display_title ?? item.external_id}>
                {item.display_title ?? item.external_id}
              </p>
              <p className="text-xs text-gray-400">
                {sourceLabel(item.source_type)} · {item.updated_at?.slice(0, 10)}
              </p>
            </div>
          ))}
        </Panel>
      </div>

      <Panel title="최근 실패 목록">
        {failuresLoading && <p className="text-xs text-gray-400 py-2">불러오는 중...</p>}
        {!failuresLoading && failures.length === 0 && <EmptyRow />}
        {!failuresLoading && failures.map((f) => (
          <div key={f.id} className="py-2 border-b text-sm">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">{sourceLabel(f.source_type)}</span>
              {f.page != null && <span className="text-xs text-gray-400">{f.page}페이지</span>}
              <span className="text-xs text-red-500">{f.error_type}</span>
            </div>
            <p className="text-gray-700 truncate" title={f.display_title ?? f.external_id ?? ""}>
              {f.display_title ?? f.external_id ?? "(문서명 없음)"}
            </p>
            {f.error_message && (
              <p className="text-xs text-gray-400 truncate" title={f.error_message}>
                {f.error_message}
              </p>
            )}
            <p className="text-xs text-gray-300">{formatDateTime(f.created_at)}</p>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function SummaryCard({ label, value }) {
  return (
    <div className="bg-white border rounded-xl p-4 shadow-sm">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-gray-800">{value}</p>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <div className="bg-white border rounded-xl p-4 shadow-sm">
      <p className="text-sm font-semibold text-gray-700 mb-3">{title}</p>
      {children}
    </div>
  );
}

function EmptyRow() {
  return <p className="text-xs text-gray-400 py-2">항목 없음</p>;
}

function formatDateTime(value) {
  return value?.slice(0, 19).replace("T", " ");
}

function sourceLabel(sourceType) {
  return SOURCE_OPTIONS.find((item) => item.value === sourceType)?.label ?? sourceType;
}

function syncStatusLabel(status) {
  if (status === "queued") return "대기 중";
  if (status === "running") return "진행 중";
  if (status === "success") return "완료";
  if (status === "no_changes") return "최신 상태";
  if (status === "failed") return "실패";
  if (status === "cancelled") return "중지됨";
  return status ?? "미실행";
}

function describeSourceState(source) {
  if (!source?.last_sync_status) return "최신화 기록 없음";
  if (source.last_sync_status === "running") {
    return `진행 중${formatProgressSummary(source)}`;
  }
  if (source.last_sync_status === "queued") return "대기 중";
  if (source.last_sync_status === "cancelled") return "중지됨";
  return source.last_sync_message ?? syncStatusLabel(source.last_sync_status);
}

function formatProgressSummary(source) {
  if (!source) return "";

  const fetched = source.fetched_count ?? 0;
  const total = source.total_count;
  const page = source.current_page;

  if (total) {
    return ` · ${fetched.toLocaleString()} / ${total.toLocaleString()}건 확인${
      page ? ` (${page}페이지)` : ""
    }`;
  }
  if (fetched > 0) {
    return ` · ${fetched.toLocaleString()}건 확인${page ? ` (${page}페이지)` : ""}`;
  }
  if (page) {
    return ` · ${page}페이지`;
  }
  return "";
}

function formatLastRunLabel(source) {
  if (!source?.last_synced_at) return "아직 실행 기록 없음";

  const label =
    source.last_sync_status === "success" || source.last_sync_status === "no_changes"
      ? "마지막 최신화"
      : "마지막 실행";
  return `${label} ${formatDateTime(source.last_synced_at)}`;
}
