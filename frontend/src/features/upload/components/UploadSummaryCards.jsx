import { Card } from '@/shared/ui/card'
import { CheckCircle2, Clock3, XCircle } from 'lucide-react'

const STATUS_CARDS = [
  { key: 'inProgress', label: '진행중', icon: Clock3, tone: 'text-primary' },
  { key: 'done', label: '성공', icon: CheckCircle2, tone: 'text-emerald-600' },
  { key: 'failed', label: '실패', icon: XCircle, tone: 'text-destructive' },
]

export default function UploadSummaryCards({ counts }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {STATUS_CARDS.map(({ key, label, icon: Icon, tone }) => (
        <Card key={key} className="p-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-muted-foreground">{label}</p>
              <p className="mt-2 text-2xl font-bold">{counts[key]}</p>
            </div>
            <Icon size={18} className={tone} />
          </div>
        </Card>
      ))}
    </div>
  )
}
