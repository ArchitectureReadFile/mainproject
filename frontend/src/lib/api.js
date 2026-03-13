import axiosInstance from './axios'


export async function fetchDocuments({ skip = 0, limit = 5, keyword = "", status = "", viewType = "my", category = "전체" }) {
  const { data } = await axiosInstance.get('/documents', {
    params: { skip, limit, keyword, status, view_type: viewType, category }
  })
  return data
}

export async function fetchDocumentDetail(id) {
  const { data } = await axiosInstance.get(`/documents/${id}`)
  return data
}

export async function downloadSummaryPdf(summaryId, caseNumber, summaryTitle) {
  const response = await axiosInstance.get(`/summaries/${summaryId}/download`, {
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new window.Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", `${caseNumber || summaryTitle || summaryId}_요약.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}