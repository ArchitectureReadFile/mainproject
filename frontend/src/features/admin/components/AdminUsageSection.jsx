export default function AdminUsageSection({ usage }) {
  const { service_usage, rag_usage } = usage;
  const storagePercent = Math.round((service_usage.storage.used_gb / service_usage.storage.limit_gb) * 100);

  return (
    <div className="space-y-6">
      {/* 서비스 사용량 */}
      <SectionBlock title="서비스 사용량">
        <div className="space-y-5">
          {/* 저장소 */}
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">저장소</span>
              <span className="text-gray-500">{service_usage.storage.used_gb} GB / {service_usage.storage.limit_gb} GB</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full"
                style={{ width: `${storagePercent}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 mt-1">{storagePercent}% 사용 중</p>
          </div>

          {/* 일별 업로드 추이 */}
          <div>
            <p className="text-xs text-gray-500 mb-2">일별 업로드 추이 (최근 7일)</p>
            <MiniBarChart
              data={service_usage.daily_uploads}
              valueKey="count"
              labelKey="date"
              color="bg-blue-300"
            />
          </div>

          {/* 문서 처리 상태 분포 */}
          <div>
            <p className="text-xs text-gray-500 mb-2">문서 처리 상태</p>
            <StatusBadgeRow jobs={service_usage.document_jobs} />
          </div>
        </div>
      </SectionBlock>

      {/* RAG 사용량 */}
      <SectionBlock title="RAG 사용량">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <StatCard label="판례 수" value={rag_usage.precedent_count.toLocaleString()} />
            <StatCard label="벡터 저장소" value={`${(rag_usage.vector_storage_mb / 1024).toFixed(1)} GB`} />
          </div>

          {/* 인덱스 처리 상태 분포 */}
          <div>
            <p className="text-xs text-gray-500 mb-2">인덱스 처리 상태</p>
            <StatusBadgeRow jobs={rag_usage.index_jobs} />
          </div>
        </div>
      </SectionBlock>
    </div>
  );
}

function SectionBlock({ title, children }) {
  return (
    <div className="bg-white border rounded-xl p-5 shadow-sm">
      <p className="text-sm font-semibold text-gray-700 mb-4">{title}</p>
      {children}
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4 border">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-xl font-bold text-gray-800">{value}</p>
    </div>
  );
}

function StatusBadgeRow({ jobs }) {
  const total = Object.values(jobs).reduce((a, b) => a + b, 0);
  const config = {
    DONE: { label: "완료", color: "bg-green-100 text-green-700" },
    PROCESSING: { label: "처리 중", color: "bg-blue-100 text-blue-700" },
    FAILED: { label: "실패", color: "bg-red-100 text-red-600" },
  };
  return (
    <div className="flex gap-3 flex-wrap">
      {Object.entries(jobs).map(([key, count]) => (
        <div key={key} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${config[key]?.color ?? "bg-gray-100 text-gray-600"}`}>
          <span>{config[key]?.label ?? key}</span>
          <span className="font-bold">{count.toLocaleString()}</span>
          <span className="opacity-60">({Math.round((count / total) * 100)}%)</span>
        </div>
      ))}
    </div>
  );
}

function MiniBarChart({ data, valueKey, labelKey, color }) {
  const max = Math.max(...data.map((d) => d[valueKey]));
  return (
    <div className="flex items-end gap-1 h-16">
      {data.map((d, i) => {
        const height = Math.round((d[valueKey] / max) * 100);
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-1">
            <div
              className={`w-full ${color} rounded-t`}
              style={{ height: `${height}%` }}
              title={`${d[labelKey]}: ${d[valueKey]}건`}
            />
            <span className="text-[9px] text-gray-400 truncate w-full text-center">
              {d[labelKey].slice(5)}
            </span>
          </div>
        );
      })}
    </div>
  );
}