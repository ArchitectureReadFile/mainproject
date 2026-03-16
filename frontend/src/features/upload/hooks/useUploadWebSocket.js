/* global WebSocket */
import { useCallback, useEffect, useRef } from 'react'

const WS_RECONNECT_DELAY = 3000

export function useUploadWebSocket({ userId, onMessage, isRunning }) {
  const wsRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const shouldConnectRef = useRef(false)

  const connect = useCallback(() => {
    if (!userId || !shouldConnectRef.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/ws/upload/${userId}`)

    ws.onopen = () => {
      wsRef.current = ws
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type !== 'ping') {
          onMessage(data)
        }
      } catch {
        // 파싱 실패 무시
      }
    }

    ws.onclose = () => {
      wsRef.current = null
      if (shouldConnectRef.current) {
        reconnectTimerRef.current = setTimeout(connect, WS_RECONNECT_DELAY)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [userId, onMessage])

  useEffect(() => {
    if (isRunning) {
      shouldConnectRef.current = true
      connect()
    } else {
      shouldConnectRef.current = false
      clearTimeout(reconnectTimerRef.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [isRunning, connect])

  useEffect(() => {
    return () => {
      shouldConnectRef.current = false
      clearTimeout(reconnectTimerRef.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [])
}