const EXPORT_INTENT_STORAGE_KEY = 'workspace-export-intent'
export const EXPORT_INTENT_UPDATED_EVENT = 'workspace-export-intent-updated'

/**
 * export intent를 저장한다.
 */
export function setStoredExportIntent(intent) {
    sessionStorage.setItem(
        EXPORT_INTENT_STORAGE_KEY,
        JSON.stringify(intent),
    )

    window.dispatchEvent(new window.CustomEvent(EXPORT_INTENT_UPDATED_EVENT))
}

/**
 * export intent를 조회한다.
 */
export function getStoredExportIntent() {
    const raw = sessionStorage.getItem(EXPORT_INTENT_STORAGE_KEY)
    if (!raw) return null

    try {
        return JSON.parse(raw)
    } catch {
        sessionStorage.removeItem(EXPORT_INTENT_STORAGE_KEY)
        return null
    }
}

/**
 * export intent를 삭제한다.
 */
export function clearStoredExportIntent() {
    sessionStorage.removeItem(EXPORT_INTENT_STORAGE_KEY)
    window.dispatchEvent(new window.CustomEvent(EXPORT_INTENT_UPDATED_EVENT))
}
