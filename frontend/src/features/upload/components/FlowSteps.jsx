export default function FlowSteps() {
  const steps = [
    ['1', 'PDF 업로드', '판례 문서를 선택하여 업로드'],
    ['2', 'AI 요약 생성', '핵심 내용 요약 및 처리'],
    ['3', '검색 가능', '유사 판례 빠르게 찾기'],
  ]

  return (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
      {steps.map(([step, title, desc]) => (
        <div key={step} className="flex flex-col items-center text-center gap-2 p-6 rounded-xl border bg-muted/40">
          <div className="w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">
            {step}
          </div>
          <p className="text-sm font-semibold">{title}</p>
          <p className="text-xs text-muted-foreground">{desc}</p>
        </div>
      ))}
    </section>
  )
}