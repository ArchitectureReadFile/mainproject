import {
  Bot,
  CheckCheck,
  FileText,
  MessageSquareText,
  ShieldAlert,
  Trash2,
} from "lucide-react";

export default function AdminDocumentAiSection({ usage }) {
  const { service_usage } = usage;
  const { document_overview, chat_overview, daily_uploads, document_jobs } = service_usage;
  const latestUploads = daily_uploads?.[daily_uploads.length - 1]?.count ?? 0;
  const totalProcessing =
    document_jobs.DONE + document_jobs.PROCESSING + document_jobs.FAILED;
  const failureRate = totalProcessing
    ? Math.round((document_jobs.FAILED / totalProcessing) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          icon={FileText}
          label="전체 문서"
          value={document_overview.total_documents.toLocaleString()}
          hint="워크스페이스 문서 전체 수"
          tone="sky"
        />
        <MetricCard
          icon={CheckCheck}
          label="요약 완료"
          value={document_overview.summary_completed_documents.toLocaleString()}
          hint="AI 요약 생성이 끝난 문서"
          tone="emerald"
        />
        <MetricCard
          icon={Bot}
          label="처리 중"
          value={document_jobs.PROCESSING.toLocaleString()}
          hint="현재 AI가 처리 중인 문서"
          tone="amber"
        />
        <MetricCard
          icon={Trash2}
          label="삭제 예정"
          value={document_overview.delete_pending_documents.toLocaleString()}
          hint="삭제 유예 중인 문서"
          tone="rose"
        />
        <MetricCard
          icon={MessageSquareText}
          label="오늘 업로드"
          value={latestUploads.toLocaleString()}
          hint="최근 일자 기준 업로드 수"
          tone="violet"
        />
      </section>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.4fr,1fr]">
        <Panel title="문서 처리 상태">
          <div className="grid gap-3 md:grid-cols-3">
            <StatusTile
              label="완료"
              value={document_jobs.DONE}
              helper="요약/처리가 정상 완료된 문서"
              tone="emerald"
            />
            <StatusTile
              label="처리 중"
              value={document_jobs.PROCESSING}
              helper="비동기 작업이 진행 중인 문서"
              tone="sky"
            />
            <StatusTile
              label="실패"
              value={document_jobs.FAILED}
              helper="재처리 또는 원인 점검이 필요한 문서"
              tone="rose"
            />
          </div>
        </Panel>

        <Panel title="챗봇 응답 현황">
          <div className="grid gap-3">
            <InsightStat
              label="총 채팅 세션"
              value={`${chat_overview.total_sessions.toLocaleString()}개`}
              helper="누적 생성된 채팅 세션 수"
            />
            <InsightStat
              label="총 AI 응답 수"
              value={`${chat_overview.total_ai_responses.toLocaleString()}건`}
              helper="ASSISTANT 메시지 기준 누적 응답"
            />
            <InsightStat
              label="최근 7일 AI 응답"
              value={`${chat_overview.last_7d_ai_responses.toLocaleString()}건`}
              helper={`오늘 ${chat_overview.today_ai_responses.toLocaleString()}건`}
            />
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.4fr,1fr]">
        <Panel title="최근 7일 업로드 추이">
          <UploadTrendChart data={daily_uploads} />
        </Panel>

        <Panel title="운영 체크 포인트">
          <div className="space-y-3">
            <InsightRow
              icon={ShieldAlert}
              label="점검 우선"
              value={document_jobs.FAILED > 0 ? "실패 문서 확인 필요" : "치명 이슈 없음"}
            />
            <InsightRow
              icon={Bot}
              label="AI 실패율"
              value={`${failureRate}%`}
            />
            <InsightRow
              icon={MessageSquareText}
              label="오늘 AI 응답"
              value={`${chat_overview.today_ai_responses.toLocaleString()}건`}
            />
          </div>
        </Panel>
      </div>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, hint, tone = "sky" }) {
  const toneClasses = {
    sky: "bg-sky-50 text-sky-700 ring-sky-100 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/20",
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
    amber: "bg-amber-50 text-amber-700 ring-amber-100 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20",
    rose: "bg-rose-50 text-rose-700 ring-rose-100 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/20",
    violet: "bg-violet-50 text-violet-700 ring-violet-100 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/20",
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

function Panel({ title, children }) {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-card-foreground">{title}</h3>
      {children}
    </section>
  );
}

function StatusTile({ label, value, helper, tone }) {
  const toneClasses = {
    emerald: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    sky: "bg-primary/10 text-primary",
    rose: "bg-destructive/10 text-destructive",
  };

  return (
    <div className="rounded-2xl bg-muted/50 px-4 py-4">
      <div className={`inline-flex rounded-full px-2 py-1 text-[11px] font-semibold ${toneClasses[tone]}`}>
        {label}
      </div>
      <p className="mt-3 text-3xl font-bold text-foreground">{value.toLocaleString()}</p>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">{helper}</p>
    </div>
  );
}

function InsightStat({ label, value, helper }) {
  return (
    <div className="rounded-2xl bg-muted/50 px-4 py-4">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-bold text-foreground">{value}</p>
      <p className="mt-2 text-xs text-muted-foreground">{helper}</p>
    </div>
  );
}

function UploadTrendChart({ data }) {
  const max = Math.max(0, ...data.map((item) => item.count));

  return (
    <div className="flex h-48 items-end gap-2">
      {data.map((item) => {
        const height = max ? Math.round((item.count / max) * 100) : 0;
        return (
          <div key={item.date} className="flex flex-1 flex-col items-center gap-2">
            <div className="text-xs text-muted-foreground">{item.count}</div>
            <div className="flex h-36 w-full items-end rounded-2xl bg-muted/50 px-2 py-2">
              <div
                className="w-full rounded-xl bg-primary/70"
                style={{ height: `${Math.max(height, item.count > 0 ? 12 : 0)}%` }}
                title={`${item.date}: ${item.count}건`}
              />
            </div>
            <div className="text-[10px] text-muted-foreground">{item.date.slice(5)}</div>
          </div>
        );
      })}
    </div>
  );
}


function InsightRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl bg-muted/50 px-4 py-3">
      <div className="rounded-xl bg-card p-2 text-muted-foreground">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
      </div>
    </div>
  );
}
