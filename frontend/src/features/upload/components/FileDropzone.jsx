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
            className={`dropzone ${isDragOver ? 'is-drag-over' : ''} ${
                isUploading ? 'is-disabled' : ''
            }`}
        >
            <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                multiple
                onChange={onFileChange}
                disabled={isUploading}
                style={{ display: 'none' }}
            />

            <div className="dropzone__icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div className="dropzone__title">클릭하여 PDF 파일 선택</div>
            <div className="dropzone__desc">또는 파일을 드래그 앤 드롭하세요</div>
        </div>
    )
}
