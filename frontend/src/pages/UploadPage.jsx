import { FileText } from 'lucide-react'
import Button from '../components/ui/Button.jsx'
import { Card } from '../components/ui/Card.jsx'
import FileDropzone from '../features/upload/components/FileDropzone.jsx'
import FileStatusItem from '../features/upload/components/FileStatusItem.jsx'
import FlowSteps from '../features/upload/components/FlowSteps.jsx'
import { useUpload } from '../context/UploadContext.jsx'
import '../styles/upload-page.css'

export default function UploadPage() {
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
    <div className="upload-page">
      <section className="upload-hero">
        <h1>판례 업로드</h1>
        <p>판례 PDF를 업로드하면 AI가 자동으로 요약하고 데이터베이스에 저장합니다.</p>
      </section>

      {/* 선택 카드 */}
      <Card className="upload-main-card">
        <div className="upload-main-card__header">
          <h2>PDF 파일 선택</h2>
          <p>파일을 드래그 앤 드롭하거나 클릭하여 선택하세요. (최대 5개)</p>
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
          <ul className="file-list" style={{ marginTop: 18 }}>
            {waitingItems.map((it) => (
              <li key={it.file.name} className="file-list__item">
                <FileText size={15} style={{ color: '#94a3b8', flexShrink: 0 }} />
                <span className="file-list__name">{it.file.name}</span>
                <span className="file-list__size" style={{ color: '#94a3b8' }}>대기 중</span>
                {!isRunning && (
                  <button
                    onClick={() => removeItem(it.file)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#cbd5e1', fontSize: 15, marginLeft: 4 }}
                  >
                    ✕
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        <Button
          onClick={handleUpload}
          disabled={waitingItems.length === 0 || isRunning}
          className="upload-submit-btn"
        >
          {isRunning ? '처리 중...' : '업로드 및 요약 생성'}
        </Button>
      </Card>

      {/* 처리 현황 카드 */}
      {started && (
        <Card className="panel-card">
          <h3 className="panel-title">처리 현황</h3>
          <ul className="file-list" style={{ marginTop: 14 }}>
            {processingItems.map((it) => (
              <FileStatusItem
                key={`${it.file.name}-${it.status}`}
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
