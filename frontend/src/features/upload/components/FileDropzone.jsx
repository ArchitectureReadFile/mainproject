import { cn } from '@/lib/utils'
import { UploadCloud } from 'lucide-react'

export default function FileDropzone({
  fileInputRef,
  isUploading,
  isDragOver,
  onOpenPicker,
  onFileChange,
  onDrop,
  onDragOver,
  onDragLeave,
}) {
  return (
    <div
      onClick={onOpenPicker}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpenPicker()
        }
      }}
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 cursor-pointer transition-colors select-none',
        isDragOver
          ? 'border-primary bg-primary/5'
          : 'border-border hover:border-primary/50 hover:bg-muted/40',
        isUploading && 'pointer-events-none opacity-50'
      )}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        multiple
        onChange={onFileChange}
        disabled={isUploading}
        className="hidden"
      />
      <UploadCloud
        size={40}
        className={cn(
          'transition-colors',
          isDragOver ? 'text-primary' : 'text-muted-foreground'
        )}
      />
      <div className="text-center">
        <p className="text-sm font-medium">클릭하여 PDF 파일 선택</p>
        <p className="text-xs text-muted-foreground mt-1">또는 파일을 드래그 앤 드롭하세요</p>
      </div>
    </div>
  )
}