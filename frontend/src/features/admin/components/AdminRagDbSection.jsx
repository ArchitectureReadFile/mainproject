import { fetchAdminPlatformFailures, stopAdminPlatform, syncAdminPlatform } from "@/shared/api/admin";
import { ERROR_CODE, getErrorMessageByCode } from "@/shared/lib/errors";
import { AlertTriangle, CheckCircle2, Clock3, Database, RefreshCcw, Rows3, XCircle } from "lucide-react";
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
  const runningSourceCount = useMemo(
    () => summary.sources.filter((item) => _RUNNING_STATUSES.has(item.last_sync_status)).length,
    [summary.sources],
  );
  const failedSourceCount = useMemo(
    () => summary.sources.filter((item) => item.last_sync_status === "failed").length,
    [summary.sources],
  );
  const lastSyncedAt = useMemo(() => {
    const values = summary.sources
      .map((item) => item.last_synced_at)
      .filter(Boolean)
      .sort()
      .reverse();
    return values[0] ?? null;
  }, [summary.sources]);

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
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        <SummaryCard
          icon={Database}
          label="전체 원천 문서"
          value={summary.total_documents.toLocaleString()}
          hint="적재된 플랫폼 원문 전체 수"
        />
        <SummaryCard
          icon={Rows3}
          label="전체 청크"
          value={summary.total_chunks.toLocaleString()}
          hint="검색용으로 분할된 chunk 수"
        />
        <SummaryCard
          icon={Clock3}
          label="진행 중 source"
          value={runningSourceCount.toLocaleString()}
          hint="최신화가 현재 동작 중인 source"
          tone="amber"
        />
        <SummaryCard
          icon={XCircle}
          label="실패 source"
          value={failedSourceCount.toLocaleString()}
          hint="마지막 실행 결과가 실패인 source"
          tone="rose"
        />
        <SummaryCard
          icon={CheckCircle2}
          label="마지막 최신화"
          value={lastSyncedAt ? formatDateTime(lastSyncedAt).slice(5, 16) : "-"}
          hint={lastSyncedAt ? formatDateTime(lastSyncedAt) : "아직 실행 기록 없음"}
          tone="emerald"
        />
      </div>

      <div className="space-y-4 rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-card-foreground">공공 데이터 전체 최신화</p>
            <p className="mt-1 text-xs text-muted-foreground">
              source별 전체 목록을 서버가 자동으로 순회해 신규 문서를 적재합니다. 새로고침을 눌러 현재 상태를 반영할 수 있습니다.
            </p>
          </div>
          <button
            onClick={onRefetch}
            disabled={actionLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
          >
            <RefreshCcw className="h-4 w-4" />
            새로고침
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {SOURCE_OPTIONS.map((option) => {
            const source = sourceMap[option.value];
            const isRunning = _RUNNING_STATUSES.has(source?.last_sync_status);
            const isThisLoading = actionLoading && activeSourceType === option.value;

            return (
              <div key={option.value} className="flex flex-col gap-3 rounded-xl border border-border bg-muted/30 p-4">
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium text-foreground">{option.label}</p>
                    <StatusBadge status={source?.last_sync_status} />
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    현재 문서 {source?.document_count ?? 0} / 청크{" "}
                    {source?.chunk_count ?? 0}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {describeSourceState(source)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatLastRunLabel(source)}
                  </p>
                </div>
                {isRunning ? (
                  <button
                    onClick={() => handleStop(option.value)}
                    disabled={isThisLoading}
                    className="rounded-lg bg-destructive px-4 py-2 text-sm text-destructive-foreground transition-colors hover:bg-destructive/90 disabled:opacity-50"
                  >
                    {isThisLoading ? "처리 중..." : "정지"}
                  </button>
                ) : (
                  <button
                    onClick={() => handleSync(option.value)}
                    disabled={actionLoading}
                    className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                  >
                    {isThisLoading ? "최신화 중..." : "전체 최신화"}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {actionError && (
          <div className="rounded-xl border border-destructive/25 bg-destructive/10 px-4 py-2">
            <p className="text-sm text-destructive">{actionError}</p>
          </div>
        )}

        {lastSync && (
          <div className="space-y-2 rounded-xl border border-border bg-muted/40 px-4 py-3">
            <div className="flex flex-wrap gap-4 text-sm">
              <span className="text-foreground">상태 {syncStatusLabel(lastSync.status)}</span>
              {"fetched" in lastSync && <span>조회 {lastSync.fetched}건</span>}
              {"created" in lastSync && <span className="text-emerald-700 dark:text-emerald-300">생성 {lastSync.created}건</span>}
              {"skipped" in lastSync && <span className="text-muted-foreground">스킵 {lastSync.skipped}건</span>}
              {"failed" in lastSync && <span className="text-destructive">실패 {lastSync.failed}건</span>}
            </div>
            <div className="text-xs text-muted-foreground">{lastSync.message}</div>
            {lastSync.status !== "cancelled" && (
              <div className="text-xs text-muted-foreground">
                작업이 백그라운드에서 계속 진행됩니다. 새로고침하면 현재 페이지와 마지막 처리 문서를 확인할 수 있습니다.
              </div>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4">
        <Panel title="최근 적재 문서">
          {summary.recent_items.length === 0 && <EmptyRow />}
          {summary.recent_items.map((item) => (
            <div key={`${item.source_type}-${item.external_id}`} className="border-b border-border py-2 text-sm last:border-b-0">
              <p
                className="truncate text-foreground"
                title={item.display_title ?? item.title ?? item.external_id}
              >
                {item.display_title ?? item.title ?? item.external_id}
              </p>
              <p className="text-xs text-muted-foreground">
                {sourceLabel(item.source_type)} · {item.updated_at?.slice(0, 10)}
              </p>
            </div>
          ))}
        </Panel>
      </div>

      <Panel title="최근 실패 목록">
        <div className="mb-3 flex items-center justify-between gap-3 rounded-xl bg-muted/40 px-4 py-3">
          <div>
            <p className="text-sm font-medium text-foreground">최근 실패 {failures.length}건</p>
            <p className="text-xs text-muted-foreground">
              반복 실패 source나 수집 오류 유형을 우선 점검하세요.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-destructive/10 px-3 py-1 text-xs font-semibold text-destructive">
            <AlertTriangle className="h-3.5 w-3.5" />
            장애 점검 영역
          </div>
        </div>
        <div className="hidden grid-cols-[0.8fr,0.7fr,1.4fr,1.8fr,0.9fr] gap-3 border-b border-border pb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground md:grid">
          <span>source</span>
          <span>유형</span>
          <span>대상</span>
          <span>오류 요약</span>
          <span>발생 시각</span>
        </div>
        {failuresLoading && <p className="py-2 text-xs text-muted-foreground">불러오는 중...</p>}
        {!failuresLoading && failures.length === 0 && <EmptyRow />}
        {!failuresLoading && failures.map((f) => (
          <div
            key={f.id}
            className="grid gap-3 rounded-xl border border-border/70 bg-muted/20 px-4 py-3 text-sm md:grid-cols-[0.8fr,0.7fr,1.4fr,1.8fr,0.9fr] md:items-start md:rounded-none md:border-0 md:border-b md:bg-transparent md:px-0 md:last:border-b-0"
          >
            <div>
              <p className="text-foreground">{sourceLabel(f.source_type)}</p>
              {f.page != null && <p className="text-xs text-muted-foreground">{f.page}페이지</p>}
            </div>
            <p className="text-sm text-destructive">{f.error_type}</p>
            <p className="truncate text-foreground" title={f.display_title ?? f.external_id ?? ""}>
              {f.display_title ?? f.external_id ?? "(문서명 없음)"}
            </p>
            <p className="truncate text-xs text-muted-foreground" title={f.error_message ?? ""}>
              {f.error_message ?? "오류 메시지 없음"}
            </p>
            <p className="text-xs text-muted-foreground/70">{formatDateTime(f.created_at)}</p>
          </div>
        ))}
      </Panel>
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value, hint, tone = "sky" }) {
  const toneClasses = {
    sky: "bg-sky-50 text-sky-700 ring-sky-100 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/20",
    amber: "bg-amber-50 text-amber-700 ring-amber-100 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20",
    rose: "bg-rose-50 text-rose-700 ring-rose-100 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/20",
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold text-foreground">{value}</p>
          <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
        </div>
        <div className={`rounded-2xl p-3 ring-1 ${toneClasses[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="mb-3 text-sm font-semibold text-card-foreground">{title}</p>
      {children}
    </div>
  );
}

function EmptyRow() {
  return <p className="py-2 text-xs text-muted-foreground">항목 없음</p>;
}

function StatusBadge({ status }) {
  const label = syncStatusLabel(status);
  const toneClasses = {
    "대기 중": "bg-amber-500/10 text-amber-700 dark:text-amber-300",
    "진행 중": "bg-primary/10 text-primary",
    "완료": "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    "최신 상태": "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    "실패": "bg-destructive/10 text-destructive",
    "중지됨": "bg-muted text-muted-foreground",
    "미실행": "bg-muted text-muted-foreground",
  };

  return (
    <span className={`inline-flex w-fit rounded-full px-2.5 py-1 text-[11px] font-semibold ${toneClasses[label] ?? "bg-muted text-muted-foreground"}`}>
      {label}
    </span>
  );
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
