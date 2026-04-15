import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Label } from '@/components/ui/Label'
import { cn } from '@/lib/utils'
import { BellRing, FileUp, Inbox, Info, MessageSquare, ShieldAlert, Trash2, Users, AtSign, UserCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getNotificationSettings, updateNotificationSetting } from '../../../features/notification/api/notification'

export default function NotificationSection() {
  const [settings, setSettings] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUpdating, setIsUpdating] = useState(false)
  const [showInfo, setShowInfo] = useState(false)

  const notificationCategories = [
    {
      title: '채팅',
      items: [
        { type: 'AI_ANSWER_COMPLETE', label: 'AI 채팅 답변', icon: MessageSquare, desc: 'AI 답변이 생성되었을 때 알림' }
      ]
    },
    {
      title: '워크스페이스',
      items: [
        { type: 'WORKSPACE_INVITED', label: '워크스페이스 초대', icon: Users, desc: '새로운 워크스페이스에 초대받았을 때 알림' },
        { type: 'WORKSPACE_MEMBER_UPDATE', label: '멤버 변경', icon: UserCheck, desc: '초대 수락, 권한 변경 등 워크스페이스 멤버 변경 알림' },
        { type: 'WORKSPACE_DELETE_NOTICE', label: '워크스페이스 삭제', icon: ShieldAlert, desc: '소속된 워크스페이스가 삭제될 예정일 때 알림' }
      ]
    },
    {
      title: '문서',
      items: [
        { type: 'COMMENT_MENTIONED', label: '댓글 멘션 알림', icon: AtSign, desc: '문서 댓글에서 누군가 나를 멘션했을 때 알림' },
        { type: 'DOCUMENT_UPLOAD_REQUESTED', label: '문서 검토 요청', icon: FileUp, desc: '내가 문서 승인자로 지정되었을 때 알림' },
        { type: 'DOCUMENT_DELETED', label: '문서 삭제 알림', icon: Trash2, desc: '내 문서가 관리자에 의해 삭제되었을 때 알림' }
      ]
    }
  ]

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await getNotificationSettings()
        const responseData = response?.data ? response.data : response
        setSettings(Array.isArray(responseData) ? responseData : [])
      } catch (error) {
        console.error(error)
      } finally {
        setIsLoading(false)
      }
    }
    fetchData()
  }, [])

  const handleToggle = async (type, field, currentValue) => {
    try {
      setIsUpdating(true)
      const safeSettings = Array.isArray(settings) ? settings : []
      const currentSetting = safeSettings.find(s => s.notification_type === type) || {
        is_enabled: true,
        is_toast_enabled: true
      }

      let newIsEnabled = currentSetting.is_enabled
      let newIsToastEnabled = currentSetting.is_toast_enabled

      if (field === 'is_enabled') {
        newIsEnabled = !currentValue
        if (!newIsEnabled) {
          newIsToastEnabled = false
        }
      } else if (field === 'is_toast_enabled') {
        newIsToastEnabled = !currentValue
        if (newIsToastEnabled) {
          newIsEnabled = true
        }
      }

      const payload = {
        notification_type: type,
        is_enabled: newIsEnabled,
        is_toast_enabled: newIsToastEnabled
      }

      await updateNotificationSetting(payload)
      const response = await getNotificationSettings()
      const responseData = response?.data ? response.data : response
      setSettings(Array.isArray(responseData) ? responseData : [])
    } catch (error) {
      console.error(error)
    } finally {
      setIsUpdating(false)
    }
  }

  const getStatus = (type, field) => {
    const safeSettings = Array.isArray(settings) ? settings : []
    const setting = safeSettings.find(s => s.notification_type === type)
    return setting ? setting[field] : true
  }

  if (isLoading) {
    return (
      <div className="flex justify-center p-8 text-zinc-500 text-sm font-medium">
        설정을 불러오는 중...
      </div>
    )
  }

  return (
    <div className="space-y-12">
      <div className="space-y-4">
        <div className="flex justify-end px-2">
          <button
            onClick={() => setShowInfo(!showInfo)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold text-zinc-400 hover:text-zinc-700 dark:hover:text-slate-200 hover:bg-zinc-100 dark:bg-slate-900/50 dark:hover:bg-slate-800 cursor-pointer transition-all active:scale-95 focus:outline-none"
          >
            <Info size={14} />
            <span>도움말</span>
          </button>
        </div>

        {showInfo && (
          <div className="bg-zinc-50 dark:bg-slate-900/50 px-6 py-4 rounded-xl border border-zinc-100 dark:border-slate-900 text-xs text-zinc-600 dark:text-slate-400 space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
            <p><strong className="text-zinc-800 dark:text-slate-200">목록 수신:</strong> 서비스 내 알림함(인박스)에 기록이 저장되어 언제든 다시 확인할 수 있습니다.</p>
            <p><strong className="text-zinc-800 dark:text-slate-200">팝업 알림:</strong> 알림 발생 즉시 30초 동안 화면 우측 하단에 실시간 토스트 팝업으로 알려줍니다.</p>
          </div>
        )}
      </div>

      <div className="space-y-16">
        {notificationCategories.map((category) => (
          <div key={category.title} className="space-y-6">
            <div className="relative flex items-center justify-center">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-zinc-200 dark:border-slate-800" />
              </div>
              <span className="relative bg-white dark:bg-background px-4 text-[11px] font-black text-zinc-400 dark:text-slate-500 uppercase tracking-[0.3em]">
                {category.title}
              </span>
            </div>

            <Card className="border-zinc-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-none rounded-xl overflow-hidden">
              <CardContent className="p-0">
                <div className="flex flex-col">
                  {category.items.map((item, index) => (
                    <div
                      key={item.type}
                      className={cn(
                        "flex flex-col md:flex-row md:items-center justify-between p-5 gap-4 hover:bg-zinc-50/50 dark:hover:bg-slate-800/20 transition-colors",
                        index !== category.items.length - 1 && "border-b border-zinc-100 dark:border-slate-800/50"
                      )}
                    >
                      <div className="flex gap-4 items-start">
                        <div className="w-8 h-8 rounded-full bg-zinc-100 dark:bg-slate-800 flex items-center justify-center shrink-0 mt-0.5">
                          <item.icon size={14} className="text-zinc-600 dark:text-slate-400" />
                        </div>
                        <div>
                          <Label className="text-sm font-bold text-zinc-800 dark:text-slate-200">{item.label}</Label>
                          <p className="text-[11px] font-medium text-zinc-400 dark:text-slate-500 mt-0.5">{item.desc}</p>
                        </div>
                      </div>

                      <div className="flex gap-2 shrink-0">
                        <Button
                          variant="outline"
                          onClick={() => handleToggle(item.type, 'is_enabled', getStatus(item.type, 'is_enabled'))}
                          disabled={isUpdating}
                          className={cn(
                            "h-9 px-4 text-xs font-bold border-zinc-200 dark:border-slate-800 hover:bg-zinc-50 dark:bg-slate-900 dark:hover:bg-slate-800 active:scale-95 transition-all",
                            getStatus(item.type, 'is_enabled') ? "text-zinc-900 dark:text-slate-100" : "text-zinc-400"
                          )}
                        >
                          <Inbox size={14} className="mr-1.5" />
                          목록 {getStatus(item.type, 'is_enabled') ? 'ON' : 'OFF'}
                        </Button>

                        <Button
                          variant="outline"
                          onClick={() => handleToggle(item.type, 'is_toast_enabled', getStatus(item.type, 'is_toast_enabled'))}
                          disabled={isUpdating}
                          className={cn(
                            "h-9 px-4 text-xs font-bold border-zinc-200 dark:border-slate-800 hover:bg-zinc-50 dark:bg-slate-900 dark:hover:bg-slate-800 active:scale-95 transition-all",
                            getStatus(item.type, 'is_toast_enabled') ? "text-zinc-900 dark:text-slate-100" : "text-zinc-400"
                          )}
                        >
                          <BellRing size={14} className="mr-1.5" />
                          팝업 {getStatus(item.type, 'is_toast_enabled') ? 'ON' : 'OFF'}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        ))}
      </div>
    </div>
  )
}