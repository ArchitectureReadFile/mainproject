/**
 * serverDocToItem.js
 *
 * 서버 문서 객체를 FileStatusItem이 소비하는 item shape으로 변환한다.
 *
 * 새로고침 후 로컬 uploadItems에 없는 서버 문서를
 * 처리 현황 리스트에 복원할 때 사용한다.
 *
 * - uploadStatus: 'uploaded' (이미 서버에 있으므로 업로드 완료 취급)
 * - summaryStatus: 서버 status에서 매핑
 * - restored: true (isSameFile에서 file.name 기준 비교로 전환)
 * - file: { name } 가짜 객체 — FileStatusItem의 it.file.name 표시 전용
 */

const STATUS_MAP = {
  PENDING: 'queued',
  PROCESSING: 'processing',
  DONE: 'done',
  FAILED: 'failed',
}

export function serverDocToItem(doc) {
  return {
    file: { name: doc.original_filename ?? doc.title ?? String(doc.id) },
    docId: doc.id,
    uploadStatus: 'uploaded',
    summaryStatus: STATUS_MAP[doc.status] ?? 'queued',
    progress: 100,
    summary: null,
    error: null,
    expanded: false,
    restored: true,
    serverDoc: doc,
  }
}
