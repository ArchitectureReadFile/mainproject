import { Button } from '@/components/ui/button'
import { FileText, X } from 'lucide-react'

export default function UploadWaitingList({ items, onRemove }) {
  if (items.length === 0) return null

  return (
    <ul className="flex flex-col gap-1.5">
      {items.map((it) => (
        <li
          key={it.file.name}
          className="flex items-center gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm"
        >
          <FileText size={15} className="text-muted-foreground shrink-0" />
          <span className="flex-1 truncate">{it.file.name}</span>
          <span className="text-xs text-muted-foreground">대기 중</span>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-muted-foreground hover:text-foreground"
            onClick={() => onRemove(it.file)}
          >
            <X size={13} />
          </Button>
        </li>
      ))}
    </ul>
  )
}
