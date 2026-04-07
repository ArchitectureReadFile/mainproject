export default function AdminUsageSection({ usage }) {
  const { service_usage, rag_usage } = usage;
  const storagePercent = service_usage.storage.limit_gb
    ? Math.round((service_usage.storage.used_gb / service_usage.storage.limit_gb) * 100)
    : 0;

  return (
    <div className="space-y-6">
      {/* 서비스 사용량 */}
      <SectionBlock title="서비스 사용량">
        <div className="space-y-5">
          <div>
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-foreground">저장소</span>
              <span className="text-muted-foreground">{service_usage.storage.used_gb} GB / {service_usage.storage.limit_gb} GB</span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted">
              <div
                className="h-2 rounded-full bg-primary"
                style={{ width: `${storagePercent}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{storagePercent}% 사용 중</p>
          </div>

          <div>
            <p className="mb-2 text-xs text-muted-foreground">일별 업로드 추이 (최근 7일)</p>
            <MiniBarChart
              data={service_usage.daily_uploads}
              valueKey="count"
              labelKey="date"
              color="bg-primary/50"
            />
          </div>

          <div>
            <p className="mb-2 text-xs text-muted-foreground">문서 처리 상태</p>
            <StatusBadgeRow jobs={service_usage.document_jobs} />
          </div>
        </div>
      </SectionBlock>

      <SectionBlock title="RAG 사용량">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <StatCard label="판례 수" value={rag_usage.precedent_count.toLocaleString()} />
            <StatCard label="벡터 저장소" value={`${(rag_usage.vector_storage_mb / 1024).toFixed(1)} GB`} />
          </div>

          <div>
            <p className="mb-2 text-xs text-muted-foreground">인덱스 처리 상태</p>
            <StatusBadgeRow jobs={rag_usage.index_jobs} />
          </div>
        </div>
      </SectionBlock>
    </div>
  );
}

function SectionBlock({ title, children }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <p className="mb-4 text-sm font-semibold text-card-foreground">{title}</p>
      {children}
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="rounded-xl border border-border bg-muted/50 p-4">
      <p className="mb-1 text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-bold text-foreground">{value}</p>
    </div>
  );
}

function StatusBadgeRow({ jobs }) {
  const total = Object.values(jobs).reduce((a, b) => a + b, 0);
  const config = {
    DONE: { label: "완료", color: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" },
    PROCESSING: { label: "처리 중", color: "bg-primary/10 text-primary" },
    FAILED: { label: "실패", color: "bg-destructive/10 text-destructive" },
  };
  return (
    <div className="flex gap-3 flex-wrap">
      {Object.entries(jobs).map(([key, count]) => (
        <div key={key} className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium ${config[key]?.color ?? "bg-muted text-muted-foreground"}`}>
          <span>{config[key]?.label ?? key}</span>
          <span className="font-bold">{count.toLocaleString()}</span>
          <span className="opacity-60">({total ? Math.round((count / total) * 100) : 0}%)</span>
        </div>
      ))}
    </div>
  );
}

function MiniBarChart({ data, valueKey, labelKey, color }) {
  const max = Math.max(0, ...data.map((d) => d[valueKey]));
  return (
    <div className="flex items-end gap-1 h-16">
      {data.map((d, i) => {
        const height = max ? Math.round((d[valueKey] / max) * 100) : 0;
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-1">
            <div
              className={`w-full ${color} rounded-t`}
              style={{ height: `${height}%` }}
              title={`${d[labelKey]}: ${d[valueKey]}건`}
            />
            <span className="w-full truncate text-center text-[9px] text-muted-foreground">
              {d[labelKey].slice(5)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
