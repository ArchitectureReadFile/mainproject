import { CheckCircle, FileText, Loader2, XCircle } from 'lucide-react'

function StatusIcon({ status }) {
  const base = { flexShrink: 0 }
  if (status === 'processing') return <Loader2 size={16} style={{ ...base, color: '#2563eb', animation: 'spin 1s linear infinite' }} />
  if (status === 'done')       return <CheckCircle size={16} style={{ ...base, color: '#15803d' }} />
  if (status === 'failed')     return <XCircle size={16} style={{ ...base, color: '#b91c1c' }} />
  return <FileText size={16} style={{ ...base, color: '#94a3b8' }} />
}

function StatusLabel({ status }) {
  const base = { fontSize: 12, fontWeight: 600 }
  if (status === 'processing') return <span style={{ ...base, color: '#2563eb' }}>처리 중...</span>
  if (status === 'done')       return <span style={{ ...base, color: '#15803d' }}>완료</span>
  if (status === 'failed')     return <span style={{ ...base, color: '#b91c1c' }}>실패</span>
  return <span style={{ ...base, color: '#94a3b8' }}>대기 중</span>
}

export default function FileStatusItem({ it, file, onToggle }) {
  return (
    <li className="file-list__item" style={{ display: 'block', padding: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px' }}>
        <StatusIcon status={it.status} />
        <span className="file-list__name" style={{ flex: 1 }}>{it.file.name}</span>
        <StatusLabel status={it.status} />
        {it.status === 'done' && (
          <button
            onClick={() => onToggle(file)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: 16, lineHeight: 1 }}
          >
            {it.expanded ? '▲' : '▼'}
          </button>
        )}
      </div>

      {it.status === 'processing' && (
        <div style={{ padding: '0 14px 12px' }}>
          <div className="upload-progress__bar">
            <div className="upload-progress__fill" style={{ width: `${it.progress}%` }} />
          </div>
        </div>
      )}

      {it.status === 'failed' && (
        <div style={{ padding: '0 14px 10px', fontSize: 13, color: '#b91c1c' }}>
          {it.error}
        </div>
      )}

      {it.status === 'done' && it.expanded && it.summary && (
        <div style={{ borderTop: '1px solid #e3eaf4', background: '#f8fbff', padding: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
            {[
              ['사건번호', it.summary.case_number],
              ['법원',     it.summary.court],
              ['판결일',   it.summary.date],
            ].map(([label, value]) => (
              <div key={label}>
                <p style={{ margin: 0, fontSize: 11, color: '#94a3b8', fontWeight: 600 }}>{label}</p>
                <p style={{ margin: '2px 0 0', fontSize: 13, fontWeight: 700, color: '#0f172a' }}>{value}</p>
              </div>
            ))}
          </div>
          <div>
            <p style={{ margin: 0, fontSize: 11, color: '#94a3b8', fontWeight: 600 }}>AI 요약</p>
            <p style={{ margin: '4px 0 0', fontSize: 14, color: '#334155', lineHeight: 1.6 }}>{it.summary.content}</p>
          </div>
        </div>
      )}
    </li>
  )
}
