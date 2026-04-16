import { Button } from '@/shared/ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/Dialog'
import FileStatusItem from './FileStatusItem.jsx'

export default function UploadProgressDialog({
  open,
  items,
  canCancel,
  onClose,
}) {
  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>문서 업로드</DialogTitle>
          <DialogDescription>
            선택한 파일을 서버에 업로드합니다. 업로드 중 닫으면 아직 전송 중인 파일과 대기 파일은 취소되며, 이미 업로드된 문서는 서버에서 계속 처리됩니다.
          </DialogDescription>
        </DialogHeader>

        <ul className="flex max-h-[50vh] flex-col gap-2 overflow-y-auto">
          {items.map((it) => (
            <FileStatusItem
              key={it.file.name + '-' + it.uploadStatus}
              it={it}
            />
          ))}
        </ul>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {canCancel ? '업로드 취소 후 닫기' : '닫기'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
