import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getNotifications, markAsRead as apiMarkAsRead, markAllAsRead as apiMarkAllAsRead, deleteNotification as apiDeleteNotification } from '../api/notification'
import { useAuth } from '../../auth'
import { showNotificationToast } from '../utils/NotificationToastUtil'

const toKSTDisplay = (dateStr) => {
  const date = new Date(dateStr)
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
      console.error('Failed to fetch notifications', error)
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
      console.error('Failed to load more notifications', error)
    } finally {
      setIsLoadingMore(false)
    }
  }, [isAuthenticated, hasMore, isLoadingMore, notifications.length])

  const markAsRead = useCallback(async (id) => {
    try {
      await apiMarkAsRead(id)
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch (error) {
      console.error('Failed to mark notification as read', error)
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
      console.error('Failed to delete notification', error)
    }
  }, [notifications])

  const handleNavigate = useCallback((n) => {
    if (!n.is_read) markAsRead(n.id)

    if (n.target_type === 'chat') {
      navigate(`/?sessionId=${n.target_id}`)
    } else if (n.target_type === 'group' && n.target_id) {
      navigate(`/workspace/${n.target_id}`)
    }
  }, [navigate, markAsRead])

  const connectWebSocket = useCallback(() => {
    if (!isAuthenticated || !user?.id) return
    
    if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
      return
    }

    const wsUrl = `ws://localhost:8000/api/ws/notifications/${user.id}`
    ws.current = new WebSocket(wsUrl)

    ws.current.onmessage = (event) => {
      try {
        const rawNotification = JSON.parse(event.data)
        const notification = {
          ...rawNotification,
          displayTime: toKSTDisplay(rawNotification.created_at || new Date())
        }
        
        setNotifications(prev => [notification, ...prev]) 
        setUnreadCount(prev => prev + 1)
        
        if (userRef.current?.is_toast_notification_enabled !== false) {
            showNotificationToast(notification, handleNavigate, userRef.current)
        }
      } catch (e) {
        console.error('Error parsing notification message', e)
      }
    }

    ws.onerror = (error) => console.error('Notification WebSocket error:', error)
  }, [isAuthenticated, user?.id, handleNavigate]) 

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  useEffect(() => {
    connectWebSocket()
    return () => {
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
      console.error('Failed to mark all as read', error)
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
    isLoadingMore
  }
}