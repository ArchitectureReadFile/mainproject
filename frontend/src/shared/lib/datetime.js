const KOREA_LOCALE = 'ko-KR'
const KOREA_TIME_ZONE = 'Asia/Seoul'

/**
 * UTC naive 문자열을 UTC 시각으로 해석해 Date 객체로 변환한다.
 */
export function parseUtcNaiveDate(value) {
    if (!value) return null

    const safeValue =
        typeof value === 'string' && !value.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(value)
            ? `${value}Z`
            : value

    const date = new Date(safeValue)
    return Number.isNaN(date.getTime()) ? null : date
}

/**
 * UTC naive 문자열을 한국 날짜 문자열로 변환한다.
 */
export function formatKoreanDate(value) {
    const date = parseUtcNaiveDate(value)
    if (!date) return '-'

    return date.toLocaleDateString(KOREA_LOCALE, {
        timeZone: KOREA_TIME_ZONE,
    })
}

/**
 * UTC naive 문자열을 한국 날짜/시간 문자열로 변환한다.
 */
export function formatKoreanDateTime(value) {
    const date = parseUtcNaiveDate(value)
    if (!date) return '-'

    return date.toLocaleString(KOREA_LOCALE, {
        timeZone: KOREA_TIME_ZONE,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
    })
}

/**
 * UTC naive 문자열 기준으로 한국 시간 D-Day를 계산한다.
 */
export function calcKoreanDday(value) {
    const targetDate = parseUtcNaiveDate(value)
    if (!targetDate) return null

    const diff = Math.ceil((targetDate - new Date()) / (1000 * 60 * 60 * 24))
    return diff <= 0 ? 'D-0' : `D-${diff}`
}
