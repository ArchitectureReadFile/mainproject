import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { FileText, X } from 'lucide-react'
import { UploadProvider, useUpload } from '../../features/upload/context/UploadContext.jsx'
import FileDropzone from '../../features/upload/components/FileDropzone.jsx'
import FileStatusItem from '../../features/upload/components/FileStatusItem.jsx'
import FlowSteps from '../../features/upload/components/FlowSteps.jsx'

function UploadPageInner() {
  const {
    fileInputRef,
    isDragOver,
    isRunning,
    started,
    waitingItems,
    processingItems,
    handleFileChange,
    handleDrop,
    handleDragOver,
    handleDragLeave,
    openFilePicker,
    removeItem,
    toggleExpand,
    handleUpload,
  } = useUpload()

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 flex flex-col gap-6">

      {/* 히어로 */}
      <section className="text-center flex flex-col gap-2">
        <h1 className="text-2xl font-bold">판례 업로드</h1>
        <p className="text-sm text-muted-foreground">
          판례 PDF를 업로드하면 AI가 자동으로 요약하고 데이터베이스에 저장합니다.
        </p>
      </section>

      {/* 파일 선택 카드 */}
      <Card className="p-6 flex flex-col gap-4">
        <div>
          <h2 className="text-base font-semibold">PDF 파일 선택</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            파일을 드래그 앤 드롭하거나 클릭하여 선택하세요. (최대 5개)
          </p>
        </div>

        {!isRunning && waitingItems.length < 5 && (
          <FileDropzone
            fileInputRef={fileInputRef}
            isUploading={isRunning}
            isDragOver={isDragOver}
            onOpenPicker={openFilePicker}
            onFileChange={handleFileChange}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          />
        )}

        {waitingItems.length > 0 && (
          <ul className="flex flex-col gap-1.5">
            {waitingItems.map((it) => (
              <li
                key={it.file.name}
                className="flex items-center gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm"
              >
                <FileText size={15} className="text-muted-foreground shrink-0" />
                <span className="flex-1 truncate">{it.file.name}</span>
                <span className="text-xs text-muted-foreground">대기 중</span>
                {!isRunning && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 text-muted-foreground hover:text-foreground"
                    onClick={() => removeItem(it.file)}
                  >
                    <X size={13} />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}

        <Button
          onClick={handleUpload}
          disabled={waitingItems.length === 0 || isRunning}
          className="w-full"
        >
          {isRunning ? '처리 중...' : '업로드 및 요약 생성'}
        </Button>
      </Card>

      {/* 처리 현황 */}
      {started && (
        <Card className="p-6 flex flex-col gap-3">
          <h3 className="text-base font-semibold">처리 현황</h3>
          <ul className="flex flex-col gap-2">
            {processingItems.map((it) => (
              <FileStatusItem
                key={it.file.name + '-' + it.status}
                it={it}
                file={it.file}
                onToggle={toggleExpand}
              />
            ))}
          </ul>
        </Card>
      )}

      <FlowSteps />
    </div>
  )
}

export default function UploadPage() {
  return (
    <UploadProvider>
      <UploadPageInner />
    </UploadProvider>
  )
}