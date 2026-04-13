import client from './client'

/**
 * 전체 다운로드 export job을 생성한다.
 */
export async function createExportJob(groupId) {
    const { data } = await client.post('/exports', {
        group_id: groupId,
    })
    return data
}

/**
 * export job 상태를 조회한다.
 */
export async function getExportJob(jobId) {
    const { data } = await client.get(`/exports/${jobId}`)
    return data
}

/**
 * 진행 중 export job을 취소한다.
 */
export async function cancelExportJob(jobId) {
    const { data } = await client.post(`/exports/${jobId}/cancel`)
    return data
}

/**
 * export ZIP 다운로드 URL을 반환한다.
 */
export function getExportDownloadUrl(jobId) {
    return `/api/exports/${jobId}/download`
}


/**
 * 그룹의 최근 export job을 조회한다.
 */
export async function getLatestExportJob(groupId) {
    const { data } = await client.get('/exports/latest', {
        params: { group_id: groupId },
    })
    return data
}