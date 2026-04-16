import client from '@/shared/api/client'

export async function createExportJob(groupId) {
    const { data } = await client.post('/exports', { group_id: groupId })
    return data
}

export async function getExportJob(jobId) {
    const { data } = await client.get(`/exports/${jobId}`)
    return data
}

export async function cancelExportJob(jobId) {
    const { data } = await client.post(`/exports/${jobId}/cancel`)
    return data
}

export function getExportDownloadUrl(jobId) {
    return `/api/exports/${jobId}/download`
}

export async function getLatestExportJob(groupId) {
    const { data } = await client.get('/exports/latest', {
        params: { group_id: groupId },
    })
    return data
}
