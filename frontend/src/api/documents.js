import client from './client'

export async function downloadSummaryPdf(summaryId, caseNumber, summaryTitle) {
  const response = await client.get(`/summaries/${summaryId}/download`, {
    responseType: 'blob',
  })

  const url = window.URL.createObjectURL(new window.Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `${caseNumber || summaryTitle || summaryId}_요약.pdf`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
