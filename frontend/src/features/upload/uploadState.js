export const MAX_FILES = 5

export const isSameFile = (item, file) =>
  item.restored ? item.file.name === file.name : item.file === file

export const makeItem = (file) => ({
  file,
  docId: null,
  status: 'waiting',
  progress: 0,
  summary: null,
  error: null,
  expanded: false,
  restored: false,
})

export const makeRestoredItem = (saved) => ({
  file: { name: saved.file_name },
  docId: saved.doc_id ?? null,
  status: saved.status,
  progress: saved.status === 'done' ? 100 : saved.status === 'processing' ? 35 : 0,
  summary: saved.summary ?? null,
  error: saved.error ?? null,
  expanded: false,
  restored: true,
})
