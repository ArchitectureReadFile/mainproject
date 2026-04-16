export default function Footer() {
  return (
    <footer className="border-t border-border bg-background/80">
      <div className="max-w-[1100px] mx-auto px-6 pt-4 pb-7">
        <div className="flex justify-between items-center flex-wrap gap-3">
          <p className="m-0 font-bold text-foreground">READLAW</p>
          <p className="m-0 text-sm text-muted-foreground">챗봇 · 워크스페이스 · 문서 요약</p>
        </div>
        <p className="mt-2.5 text-xs text-muted-foreground">© 2026 참고용 도구입니다. 법률 자문을 대체하지 않습니다.</p>
      </div>
    </footer>
  )
}
