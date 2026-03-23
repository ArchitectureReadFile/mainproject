export const MAX_FILES = 5

export const isSameFile = (item, file) =>
  item.restored ? item.file.name === file.name : item.file === file

export const makeItem = (file) => ({
  file,
  docId: null,
  uploadStatus: 'waiting',
  summaryStatus: 'idle',
  progress: 0,
  summary: null,
  error: null,
  expanded: false,
  restored: false,
})
