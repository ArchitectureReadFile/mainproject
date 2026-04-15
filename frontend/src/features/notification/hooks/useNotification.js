import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getNotifications, markAsRead as apiMarkAsRead, markAllAsRead as apiMarkAllAsRead, deleteNotification as apiDeleteNotification } from '../api/notification'
import { useAuth } from '../../auth'
import { showNotificationToast } from '../utils/NotificationToastUtil'

const toKSTDisplay = (dateStr) => {
  if (!dateStr) return ''
  let safeDateStr = dateStr
  if (!safeDateStr.endsWith('Z') && !safeDateStr.includes('+')) {
    safeDateStr += 'Z'
  }
  const date = new Date(safeDateStr)
  return date.toLocaleString('ko-KR', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

export const useNotification = () => {
  const { user, isAuthenticated } = useAuth()
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)

  const [hasMore, setHasMore] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  const ws = useRef(null)
  const intentionalClose = useRef(false)
  const reconnectTimer = useRef(null)
  const navigate = useNavigate()

  const userRef = useRef(user)
  useEffect(() => {
    userRef.current = user
  }, [user])

  const fetchNotifications = useCallback(async () => {
    if (!isAuthenticated) return
    try {
      const response = await getNotifications(0, 20)
      const data = response.data.map(n => ({
        ...n,
        displayTime: toKSTDisplay(n.created_at)
      }))
      setNotifications(data)
      setUnreadCount(data.filter(n => !n.is_read).length)
      setHasMore(data.length === 20)
    } catch (error) {
      console.error(error)
    }
  }, [isAuthenticated])

  const loadMoreNotifications = useCallback(async () => {
    if (!isAuthenticated || !hasMore || isLoadingMore) return

    setIsLoadingMore(true)
    try {
      const response = await getNotifications(notifications.length, 20)
      const data = response.data.map(n => ({
        ...n,
        displayTime: toKSTDisplay(n.created_at)
      }))

      setNotifications(prev => {
        const newItems = data.filter(d => !prev.some(p => p.id === d.id))
        return [...prev, ...newItems]
      })

      const newUnreadCount = data.filter(n => !n.is_read).length
      if (newUnreadCount > 0) {
        setUnreadCount(prev => prev + newUnreadCount)
      }

      setHasMore(data.length === 20)
    } catch (error) {
      console.error(error)
    } finally {
      setIsLoadingMore(false)
    }
  }, [isAuthenticated, hasMore, isLoadingMore, notifications.length])

  const updateInviteStatus = useCallback((id, status) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, inviteStatus: status } : n))
  }, [])

  const markAsRead = useCallback(async (id) => {
    try {
      await apiMarkAsRead(id)
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch (error) {
      console.error(error)
    }
  }, [])

  const deleteNotification = useCallback(async (id) => {
    try {
      await apiDeleteNotification(id)
      const target = notifications.find(n => n.id === id)
      if (target && !target.is_read) {
        setUnreadCount(prev => Math.max(0, prev - 1))
      }
      setNotifications(prev => prev.filter(n => n.id !== id))
    } catch (error) {
      console.error(error)
    }
  }, [notifications])

  const handleNavigate = useCallback((n) => {
    const type = n.notification_type || n.type

    if (!n.is_read) {
      if (type !== 'WORKSPACE_INVITED') {
        markAsRead(n.id)
      }
    }

    if (type === 'WORKSPACE_KICKED') {
      return
    }

    if (n.target_type === 'chat' && n.target_id) {
      navigate(`/?sessionId=${n.target_id}`)
      return
    }

    if (type === 'COMMENT_MENTIONED' && n.target_type?.startsWith('doc_comment:')) {
      const parts = n.target_type.split(':')
      const page = parts[1]
      const scope = parts[2]
      navigate(`/workspace/${n.group_id}/documents/${n.target_id}?tab=approvals&page=${page}&comment_scope=${scope}`)
      return
    }

    if (n.target_type === 'group' && n.target_id) {
      const groupId = n.target_id

      switch (type) {
        case 'WORKSPACE_INVITED':
          navigate(`/workspace/${groupId}?tab=workspace`)
          break
        case 'WORKSPACE_MEMBER_UPDATE':
          navigate(`/workspace/${groupId}?tab=members`)
          break
        case 'DOCUMENT_UPLOAD_REQUESTED':
          navigate(`/workspace/${groupId}?tab=approval`)
          break
        case 'DOCUMENT_DELETED':
          navigate(`/workspace/${groupId}?tab=trash`)
          break
        case 'WORKSPACE_DELETE_NOTICE':
          navigate(`/workspace/${groupId}?tab=workspace`)
      }
    }
  }, [navigate, markAsRead])

  const connectWebSocket = useCallback(() => {
    if (!isAuthenticated || !user?.id) return

    if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${window.location.host}/api/ws/notifications/${user.id}`
    ws.current = new WebSocket(wsUrl)

    ws.current.onmessage = (event) => {
      try {
        const rawNotification = JSON.parse(event.data)
        const notification = {
          ...rawNotification,
          displayTime: toKSTDisplay(rawNotification.created_at || new Date().toISOString())
        }

        setNotifications(prev => [notification, ...prev])
        setUnreadCount(prev => prev + 1)

        if (notification.is_toast_enabled !== false) {
          showNotificationToast(notification, handleNavigate, updateInviteStatus, markAsRead, userRef.current)
        }

      } catch (e) {
        console.error(e)
      }
    }

    ws.current.onerror = (error) => console.error(error)

    ws.current.onclose = () => {
      if (intentionalClose.current) return
      reconnectTimer.current = setTimeout(() => {
        connectWebSocket()
      }, 3000)
    }
  }, [isAuthenticated, user?.id, handleNavigate, updateInviteStatus, markAsRead])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  useEffect(() => {
    connectWebSocket()
    return () => {
      intentionalClose.current = true
      clearTimeout(reconnectTimer.current)
      if (ws.current) {
        ws.current.close()
        ws.current = null
      }
    }
  }, [connectWebSocket])

  const markAllAsRead = async () => {
    try {
      await apiMarkAllAsRead()
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
      setUnreadCount(0)
    } catch (error) {
      console.error(error)
    }
  }

  return {
    notifications,
    unreadCount,
    markAsRead,
    deleteNotification,
    markAllAsRead,
    handleNavigate,
    fetchNotifications,
    loadMoreNotifications,
    hasMore,
    isLoadingMore,
    updateInviteStatus
  }
}
