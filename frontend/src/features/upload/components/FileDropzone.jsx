import { cn } from '@/lib/utils'
import { IoCloudUploadOutline } from 'react-icons/io5'

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
        'flex cursor-pointer select-none flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 transition-colors',
        isDragOver
          ? 'border-primary bg-primary/5'
          : 'border-border hover:border-primary/50 hover:bg-muted/40',
        isUploading && 'pointer-events-none opacity-50'
      )}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.doc,.docx"
        multiple
        onChange={onFileChange}
        disabled={isUploading}
        className="hidden"
      />
      <IoCloudUploadOutline
        size={40}
        className={cn(
          'transition-colors',
          isDragOver ? 'text-primary' : 'text-muted-foreground'
        )}
      />
      <div className="text-center">
        <p className="text-sm font-medium">클릭하여 업로드할 문서 선택</p>
        <p className="mt-1 text-xs text-muted-foreground">
          PDF, DOC, DOCX 파일을 드래그 앤 드롭하거나 선택하세요
        </p>
      </div>
    </div>
  )
}