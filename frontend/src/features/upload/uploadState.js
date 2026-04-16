export const MAX_FILES = 5

/**
 * isSameFile(item, file)
 *
 * item: uploadItems/items 안의 레코드
 * file: File 객체 또는 { name } 형태의 객체
 *
 * restored 항목({ name } 가짜 객체)은 레퍼런스 비교가 불가능하므로
 * item.restored 일 때는 name 문자열 기준으로 비교한다.
 * removeItem 등 호출시 두 번째 인자를 targetItem.file로 통일하여 혼용을 막는다.
 */
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
