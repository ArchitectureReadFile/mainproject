import Button from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../../auth/context/AuthContext.jsx'

export default function DocumentCard({ item, onClick, viewType, onDelete }) {
  const { user } = useAuth()
  const [hovered, setHovered] = useState(false)

  const isAdmin = user?.role === 'ADMIN'
  const isOwner = user?.username === item.uploader
  const canDelete = isOwner || isAdmin

  return (
    <div
      className="relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {canDelete && hovered && (
        <Button
          variant="ghost"
          size="icon"
          className="absolute top-3 right-3 z-10 text-destructive hover:bg-destructive/10 hover:text-destructive"
          onClick={(e) => {
            e.stopPropagation()
            onDelete(item.id)
          }}
        >
          <Trash2 size={18} />
        </Button>
      )}

      <Card onClick={onClick}>
        <div className="px-6 py-5">
          <h3 className="text-base font-semibold mb-1.5">{item.title}</h3>

          <div className="flex gap-4 text-sm text-muted-foreground mb-2.5">
            <span>법원: {item.court_name || '-'}</span>
            <span>판결일: {item.judgment_date || '-'}</span>
            {viewType === 'all' && (
              <span>업로드: {item.uploader || '-'}</span>
            )}
          </div>

          {item.preview && (
            <p className="text-sm text-foreground/70 line-clamp-3">
              {item.preview}
            </p>
          )}
        </div>
      </Card>
    </div>
  )
}