export default function AdminOverviewSection({ stats }) {
  const {
    total_users,
    active_groups,
    premium_conversion_rate,
    ai_success_rate,
    conversion_trend,
    ai_trend,
  } = stats;

  return (
    <div className="space-y-8">
      {/* KPI 카드: 전체 회원 / PREMIUM 전환율 / 활성 워크스페이스 수 / AI 처리 성공률 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="전체 회원" value={total_users.toLocaleString()} />
        <MetricCard label="PREMIUM 전환율" value={`${premium_conversion_rate}%`} />
        <MetricCard label="활성 워크스페이스" value={active_groups.toLocaleString()} />
        <MetricCard label="AI 처리 성공률" value={`${ai_success_rate}%`} />
      </div>

      {/* 전환률 추이 */}
      {conversion_trend?.length > 0 && (
        <ChartBlock title="PREMIUM 전환률 추이 (최근 7일)">
          <MiniLineChart
            data={conversion_trend}
            valueKey="rate"
            labelKey="date"
            color="#60a5fa"
          />
        </ChartBlock>
      )}

      {/* AI 요청량 + 실패율 */}
      {ai_trend?.length > 0 && (
        <ChartBlock title="AI 요청량 / 실패율 (최근 7일)">
          <MiniBarLineChart
            data={ai_trend}
            barKey="requests"
            lineKey="failure_rate"
            labelKey="date"
          />
        </ChartBlock>
      )}
    </div>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="bg-white border rounded-xl p-4 shadow-sm">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-gray-800">{value}</p>
    </div>
  );
}

function ChartBlock({ title, children }) {
  return (
    <div className="bg-white border rounded-xl p-5 shadow-sm">
      <p className="text-sm font-semibold text-gray-700 mb-4">{title}</p>
      {children}
    </div>
  );
}

function MiniLineChart({ data, valueKey, labelKey, color = "#60a5fa" }) {
  const chartH = 80;
  const total = data.length;
  const max = Math.max(...data.map((d) => d[valueKey]));
  const min = Math.min(...data.map((d) => d[valueKey]));
  const range = max - min || 1;

  return (
    <div className="space-y-1">
      <div className="relative w-full" style={{ height: `${chartH}px` }}>
        <svg
          className="absolute inset-0 w-full h-full overflow-visible pointer-events-none"
          viewBox={`0 0 100 ${chartH}`}
          preserveAspectRatio="none"
        >
          <polyline
            points={data
              .map((d, i) => {
                const x = ((i + 0.5) / total) * 100;
                const y =
                  chartH -
                  ((d[valueKey] - min) / range) * (chartH * 0.8) -
                  chartH * 0.1;
                return `${x},${y}`;
              })
              .join(" ")}
            fill="none"
            stroke={color}
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      <div className="flex gap-1">
        {data.map((d, i) => (
          <div key={i} className="flex-1 text-center">
            <span className="text-[9px] text-gray-400">{d[labelKey].slice(5)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MiniBarLineChart({ data, barKey, lineKey, labelKey }) {
  const chartH = 80;
  const total = data.length;
  const maxBar = Math.max(...data.map((d) => d[barKey]));
  const maxLine = Math.max(...data.map((d) => d[lineKey]));
  const minLine = Math.min(...data.map((d) => d[lineKey]));
  const lineRange = maxLine - minLine || 1;

  return (
    <div className="space-y-1">
      <div className="relative w-full" style={{ height: `${chartH}px` }}>
        <div className="absolute inset-0 flex items-end gap-1">
          {data.map((d, i) => {
            const barH = Math.round((d[barKey] / maxBar) * 100);
            return (
              <div key={i} className="flex-1 flex justify-center items-end h-full">
                <div
                  className="w-1/4 bg-indigo-400 rounded-t"
                  style={{ height: `${barH}%` }}
                  title={`요청량: ${d[barKey]}`}
                />
              </div>
            );
          })}
        </div>
        <svg
          className="absolute inset-0 w-full h-full overflow-visible pointer-events-none"
          viewBox={`0 0 100 ${chartH}`}
          preserveAspectRatio="none"
        >
          <polyline
            points={data
              .map((d, i) => {
                const x = ((i + 0.5) / total) * 100;
                const y =
                  chartH -
                  ((d[lineKey] - minLine) / lineRange) * (chartH * 0.8) -
                  chartH * 0.1;
                return `${x},${y}`;
              })
              .join(" ")}
            fill="none"
            stroke="#f87171"
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      <div className="flex gap-1">
        {data.map((d, i) => (
          <div key={i} className="flex-1 text-center">
            <span className="text-[9px] text-gray-400">{d[labelKey].slice(5)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
