export default function FlowSteps() {
  const steps = [
    ['1', 'PDF 업로드', '판례 문서를 선택하여 업로드'],
    ['2', 'AI 요약 생성', '핵심 내용 요약 및 처리'],
    ['3', '검색 가능', '유사 판례 빠르게 찾기'],
  ]

  return (
    <section className="steps-grid">
      {steps.map(([step, title, desc]) => (
        <div key={step} className="step-card">
          <div className="step-card__badge">{step}</div>
          <div className="step-card__title">{title}</div>
          <div className="step-card__desc">{desc}</div>
        </div>
      ))}
    </section>
  )
}
