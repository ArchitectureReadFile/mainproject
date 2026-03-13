import Button from './Button.jsx'

export default function ConfirmModal({
  open,
  message,
  confirmLabel = '확인',
  cancelLabel = '취소',
  onConfirm,
  onCancel,
}) {
  if (!open) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div style={{ background: '#fff', borderRadius: 12, padding: 32, width: 340 }}>
        <p style={{ marginBottom: 24, fontWeight: 600, whiteSpace: 'pre-line' }}>{message}</p>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Button variant="outline" onClick={onCancel}>{cancelLabel}</Button>
          <Button onClick={onConfirm} style={{ background: '#ef4444', color: '#fff' }}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  )
}
