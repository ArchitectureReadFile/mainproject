import {
  Activity,
  BadgePercent,
  Bot,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";

export default function AdminOverviewSection({ stats }) {
  const {
    total_users,
    premium_users,
    active_groups,
    premium_conversion_rate,
    ai_success_rate,
    conversion_trend,
    ai_trend,
  } = stats;

  const latestAi = ai_trend?.[ai_trend.length - 1] ?? null;
  const latestConversion = conversion_trend?.[conversion_trend.length - 1] ?? null;
  const latestFailureRate = latestAi?.failure_rate ?? 0;
  const latestRequests = latestAi?.requests ?? 0;
  const healthTone =
    ai_success_rate >= 95
      ? "good"
      : ai_success_rate >= 80
        ? "warn"
        : "risk";
  const healthLabel =
    healthTone === "good"
      ? "안정"
      : healthTone === "warn"
        ? "주의"
        : "점검 필요";

  return (
    <div className="space-y-6">
      <OverviewHero
        totalUsers={total_users}
        premiumUsers={premium_users}
        activeGroups={active_groups}
        aiSuccessRate={ai_success_rate}
        latestRequests={latestRequests}
        latestFailureRate={latestFailureRate}
        latestConversion={latestConversion?.rate ?? premium_conversion_rate}
        healthLabel={healthLabel}
        healthTone={healthTone}
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={Users}
          label="활성 회원"
          value={total_users.toLocaleString()}
          hint="현재 활성 상태인 일반 회원 수"
          tone="sky"
        />
        <MetricCard
          icon={BadgePercent}
          label="PREMIUM 회원"
          value={premium_users.toLocaleString()}
          hint={`전환율 ${premium_conversion_rate}%`}
          tone="amber"
        />
        <MetricCard
          icon={Sparkles}
          label="활성 워크스페이스"
          value={active_groups.toLocaleString()}
          hint="현재 운영 중인 워크스페이스"
          tone="emerald"
        />
        <MetricCard
          icon={Bot}
          label="AI 처리 성공률"
          value={`${ai_success_rate}%`}
          hint={`최근 실패율 ${latestFailureRate}%`}
          tone="violet"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr,1fr]">
        <InsightPanel
          title="운영 포인트"
          items={[
            {
              label: "회원 전환",
              value: `${premium_conversion_rate}%`,
              helper: "활성 회원 대비 PREMIUM 전환 비율",
            },
            {
              label: "오늘 AI 요청",
              value: `${latestRequests.toLocaleString()}건`,
              helper: "최근 일자 기준 문서 처리 요청량",
            },
            {
              label: "AI 실패율",
              value: `${latestFailureRate}%`,
              helper: "최근 일자 기준 처리 실패 비율",
            },
          ]}
        />
        <HealthPanel
          aiSuccessRate={ai_success_rate}
          latestFailureRate={latestFailureRate}
          latestRequests={latestRequests}
          healthLabel={healthLabel}
          healthTone={healthTone}
        />
      </div>

      {conversion_trend?.length > 0 && (
        <ChartBlock
          title="PREMIUM 전환률 추이"
          description="최근 7일 동안의 누적 전환 비율입니다."
        >
          <MiniLineChart
            data={conversion_trend}
            valueKey="rate"
            labelKey="date"
            color="#60a5fa"
          />
        </ChartBlock>
      )}

      {ai_trend?.length > 0 && (
        <ChartBlock
          title="AI 요청량 및 실패율"
          description="최근 7일 기준 문서 처리 요청 수와 실패율입니다."
        >
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

function OverviewHero({
  totalUsers,
  premiumUsers,
  activeGroups,
  aiSuccessRate,
  latestRequests,
  latestFailureRate,
  latestConversion,
  healthLabel,
  healthTone,
}) {
  const toneClass = {
    good: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warn: "border-amber-200 bg-amber-50 text-amber-700",
    risk: "border-rose-200 bg-rose-50 text-rose-700",
  }[healthTone];

  return (
    <section className="overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-primary/8 via-background to-accent/40 p-6 text-foreground shadow-sm">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl space-y-3">
          <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${toneClass}`}>
            운영 상태 {healthLabel}
          </span>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">서비스 개요</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              활성 회원 {totalUsers.toLocaleString()}명, PREMIUM 회원 {premiumUsers.toLocaleString()}명,
              활성 워크스페이스 {activeGroups.toLocaleString()}개 기준으로 운영 중입니다.
              현재 AI 처리 성공률은 {aiSuccessRate}%이며 최근 일자 실패율은 {latestFailureRate}%입니다.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <HeroStat label="최근 전환율" value={`${latestConversion}%`} />
          <HeroStat label="오늘 요청" value={`${latestRequests}`} />
          <HeroStat label="활성 그룹" value={`${activeGroups}`} />
          <HeroStat label="AI 성공률" value={`${aiSuccessRate}%`} />
        </div>
      </div>
    </section>
  );
}

function HeroStat({ label, value }) {
  return (
    <div className="rounded-2xl border border-border bg-card/80 px-4 py-3 backdrop-blur-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-bold text-foreground">{value}</p>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, hint, tone = "sky" }) {
  const toneClasses = {
    sky: "bg-sky-50 text-sky-700 ring-sky-100",
    amber: "bg-amber-50 text-amber-700 ring-amber-100",
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    violet: "bg-violet-50 text-violet-700 ring-violet-100",
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

function InsightPanel({ title, items }) {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <TrendingUp className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-card-foreground">{title}</h3>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3 xl:grid-cols-1">
        {items.map((item) => (
          <div key={item.label} className="rounded-2xl bg-muted/60 px-4 py-3">
            <p className="text-xs font-medium text-muted-foreground">{item.label}</p>
            <p className="mt-1 text-lg font-bold text-foreground">{item.value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{item.helper}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function HealthPanel({
  aiSuccessRate,
  latestFailureRate,
  latestRequests,
  healthLabel,
  healthTone,
}) {
  const toneClasses = {
    good: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warn: "border-amber-200 bg-amber-50 text-amber-700",
    risk: "border-rose-200 bg-rose-50 text-rose-700",
  };

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-card-foreground">상태 요약</h3>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${toneClasses[healthTone]}`}>
          {healthLabel}
        </span>
      </div>
      <div className="mt-4 space-y-3 text-sm">
        <StatusRow label="AI 성공률" value={`${aiSuccessRate}%`} />
        <StatusRow label="최근 실패율" value={`${latestFailureRate}%`} />
        <StatusRow label="최근 요청량" value={`${latestRequests.toLocaleString()}건`} />
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-400">
        성공률과 실패율은 문서 처리 상태 기준으로 계산됩니다. 실패율이 상승하면
        모델 응답, 외부 연동, 큐 적체를 함께 점검하는 것이 좋습니다.
      </p>
    </section>
  );
}

function StatusRow({ label, value }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-muted/60 px-4 py-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold text-foreground">{value}</span>
    </div>
  );
}

function ChartBlock({ title, description, children }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="mb-4">
        <p className="text-sm font-semibold text-card-foreground">{title}</p>
        {description && <p className="mt-1 text-xs text-muted-foreground">{description}</p>}
      </div>
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
    <div className="space-y-2">
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
            <span className="text-[10px] text-muted-foreground">{d[labelKey].slice(5)}</span>
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
    <div className="space-y-2">
      <div className="relative w-full" style={{ height: `${chartH}px` }}>
        <div className="absolute inset-0 flex items-end gap-1">
          {data.map((d, i) => {
            const barH = maxBar ? Math.round((d[barKey] / maxBar) * 100) : 0;
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
            <span className="text-[10px] text-muted-foreground">{d[labelKey].slice(5)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
