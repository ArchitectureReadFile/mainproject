import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { Tabs, TabsContent } from '@/components/ui/Tabs'
import { Shield, User, Mail, AlertTriangle, Bell, BellRing } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useAuth } from '../../features/auth'
import { updateNotificationSettings } from '../../features/auth/api/authApi'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

export default function Mypage() {
  const { user, setUser } = useAuth()
  const [activeTab, setActiveTab] = useState("profile")
  const [isToastEnabled, setIsToastEnabled] = useState(user?.is_toast_notification_enabled ?? true)
  const [isUpdating, setIsUpdating] = useState(false)

  useEffect(() => {
    if (user) {
      setIsToastEnabled(user.is_toast_notification_enabled)
    }
  }, [user])

  const handleNotificationToggle = async (checked) => {
    try {
      setIsUpdating(true)
      const updatedUser = await updateNotificationSettings(checked)
      setIsToastEnabled(checked)
      setUser(updatedUser)
      toast.success(checked ? '실시간 토스트 알림이 활성화되었습니다.' : '실시간 토스트 알림이 비활성화되었습니다.')
    } catch (error) {
      console.error('Failed to update notification settings:', error)
      toast.error('알림 설정 업데이트에 실패했습니다.')
      setIsToastEnabled(!checked)
    } finally {
      setIsUpdating(false)
    }
  }

  const handleWithdrawal = () => {
    if (window.confirm("정말로 탈퇴하시겠습니까? 모든 데이터가 영구적으로 삭제되며 복구할 수 없습니다.")) {
      toast.error("회원 탈퇴 기능은 현재 준비 중입니다.")
    }
  }

  return (
    <div className="max-w-[1000px] mx-auto px-6 py-12">
      <div className="flex flex-col md:flex-row gap-8 items-start">
        <div className="w-full md:w-64 space-y-6 shrink-0">
          <div className="p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm flex flex-col items-center text-center transition-colors">
            <div className="w-20 h-24 bg-blue-50 dark:bg-blue-900/20 rounded-2xl flex items-center justify-center mb-4">
              <User size={40} className="text-blue-600 dark:text-blue-400" />
            </div>
            <h2 className="text-xl font-black text-zinc-900 dark:text-zinc-100">{user?.username}</h2>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">{user?.email}</p>
            <Badge variant="secondary" className="px-3 py-1 font-bold dark:bg-zinc-800 dark:text-zinc-300">
              {user?.role === 'ADMIN' ? '관리자 계정' : '일반 회원'}
            </Badge>
          </div>

          <div className="space-y-1">
            <Button 
              variant="ghost" 
              onClick={() => setActiveTab("profile")}
              className={cn(
                "w-full justify-start gap-3 rounded-xl font-bold h-12 transition-all",
                activeTab === "profile" 
                  ? "text-blue-600 bg-blue-50 dark:bg-blue-900/30 dark:text-blue-400" 
                  : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 dark:hover:bg-zinc-800"
              )}
            >
              <User size={18} /> 계정 정보
            </Button>
            <Button 
              variant="ghost" 
              onClick={() => setActiveTab("notification")}
              className={cn(
                "w-full justify-start gap-3 rounded-xl font-bold h-12 transition-all",
                activeTab === "notification" 
                  ? "text-blue-600 bg-blue-50 dark:bg-blue-900/30 dark:text-blue-400" 
                  : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 dark:hover:bg-zinc-800"
              )}
            >
              <Bell size={18} /> 알림 설정
            </Button>
            <Button 
              variant="ghost" 
              onClick={() => setActiveTab("security")}
              className={cn(
                "w-full justify-start gap-3 rounded-xl font-bold h-12 transition-all",
                activeTab === "security" 
                  ? "text-blue-600 bg-blue-50 dark:bg-blue-900/30 dark:text-blue-400" 
                  : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 dark:hover:bg-zinc-800"
              )}
            >
              <Shield size={18} /> 보안 및 인증
            </Button>
          </div>
        </div>

        <div className="flex-1 w-full min-h-[500px]">
          <Tabs value={activeTab} className="w-full">
            <TabsContent value="profile" className="mt-0 space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
              <Card className="border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm bg-white dark:bg-zinc-900 transition-colors">
                <CardHeader>
                  <CardTitle className="text-xl font-black dark:text-zinc-100">기본 정보</CardTitle>
                  <CardDescription className="dark:text-zinc-400">계정의 기본 정보를 확인하고 수정할 수 있습니다.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid gap-2">
                    <Label htmlFor="username" className="font-bold text-zinc-700 dark:text-zinc-300">사용자 이름</Label>
                    <div className="flex gap-2">
                      <Input id="username" defaultValue={user?.username} className="rounded-xl border-zinc-200 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100" />
                      <Button variant="outline" className="rounded-xl font-bold px-6 dark:border-zinc-600 dark:text-zinc-200 dark:hover:bg-zinc-800 dark:bg-zinc-800/50">수정</Button>
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="email" className="font-bold text-zinc-700 dark:text-zinc-300">이메일 주소</Label>
                    <div className="flex items-center gap-3 px-4 py-3 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-800 rounded-xl">
                      <Mail size={16} className="text-zinc-400" />
                      <span className="text-sm font-medium text-zinc-600 dark:text-zinc-400">{user?.email}</span>
                      <Badge className="ml-auto bg-emerald-500/10 text-emerald-600 border-none dark:bg-emerald-500/20 dark:text-emerald-400 pointer-events-none">인증됨</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="notification" className="mt-0 space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
              <Card className="border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm bg-white dark:bg-zinc-900 transition-colors">
                <CardHeader>
                  <CardTitle className="text-xl font-black dark:text-zinc-100">알림 수신 설정</CardTitle>
                  <CardDescription className="dark:text-zinc-400">실시간 답변 알림 및 서비스 소식을 관리합니다.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-2xl border border-zinc-100 dark:border-zinc-800">
                    <div className="flex gap-4 items-start">
                      <div className="w-10 h-10 bg-white dark:bg-zinc-700 rounded-xl flex items-center justify-center shadow-sm shrink-0">
                        <BellRing size={20} className="text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <Label className="text-base font-bold text-zinc-900 dark:text-zinc-100">실시간 토스트 알림</Label>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">AI 답변이 완료되거나 중요 소식이 있을 때 화면 우측 하단에 알림을 띄웁니다.</p>
                      </div>
                    </div>
                    <Button 
                      variant={isToastEnabled ? "default" : "outline"}
                      size="sm"
                      onClick={() => handleNotificationToggle(!isToastEnabled)}
                      disabled={isUpdating}
                      className={cn(
                        "rounded-xl font-bold px-6 h-9 transition-all",
                        isToastEnabled 
                          ? "bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-100 dark:shadow-none dark:bg-blue-600 dark:hover:bg-blue-700" 
                          : "text-zinc-500 border-zinc-200 dark:text-zinc-200 dark:border-zinc-600 dark:bg-zinc-800/50 dark:hover:bg-zinc-800"
                      )}
                    >
                      {isToastEnabled ? '활성화됨' : '비활성'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="security" className="mt-0 space-y-12 animate-in fade-in slide-in-from-right-4 duration-300">
              <Card className="border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-sm bg-white dark:bg-zinc-900 transition-colors">
                <CardHeader>
                  <CardTitle className="text-xl font-black dark:text-zinc-100">비밀번호 변경</CardTitle>
                  <CardDescription className="dark:text-zinc-400">보안을 위해 비밀번호를 주기적으로 변경하는 것을 권장합니다.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-2">
                    <Label className="font-bold text-zinc-700 dark:text-zinc-300">현재 비밀번호</Label>
                    <Input type="password" placeholder="현재 비밀번호 입력" className="rounded-xl dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100" />
                  </div>
                  <div className="grid gap-2">
                    <Label className="font-bold text-zinc-700 dark:text-zinc-300">새 비밀번호</Label>
                    <Input type="password" placeholder="새 비밀번호 입력" className="rounded-xl dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100" />
                  </div>
                  <div className="flex justify-center pt-2">
                    <Button variant="outline" className="rounded-xl font-bold px-6 dark:border-zinc-600 dark:text-zinc-200 dark:hover:bg-zinc-800 dark:bg-zinc-800/50">
                      비밀번호 업데이트
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <div className="space-y-4">
                <div className="flex items-center gap-2 px-2">
                  <div className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
                  <span className="text-xs font-bold text-zinc-400 uppercase tracking-widest">위험 구역</span>
                  <div className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
                </div>
                
                <Card className="border-red-200 dark:border-red-900/20 rounded-2xl shadow-sm overflow-hidden border bg-white dark:bg-zinc-900">
                  <div className="p-6 bg-red-50/30 dark:bg-red-900/10 flex flex-col md:flex-row items-center justify-between gap-6 text-center md:text-left">
                    <div className="flex flex-col md:flex-row gap-4 items-center md:items-start">
                      <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-2xl flex items-center justify-center shrink-0">
                        <AlertTriangle size={24} className="text-red-600 dark:text-red-500" />
                      </div>
                      <div>
                        <h4 className="text-lg font-black text-red-600 dark:text-red-500 mb-1">회원 탈퇴</h4>
                        <p className="text-sm text-red-500/80 dark:text-red-400/80 leading-relaxed font-medium">
                          계정을 삭제하면 모든 상담 내역, 업로드한 문서, 그리고 개인 정보가 <br className="hidden md:block" />
                          <strong className="dark:text-red-400">영구적으로 삭제</strong>되며 절대 복구할 수 없습니다.
                        </p>
                      </div>
                    </div>
                    <Button 
                      variant="destructive" 
                      onClick={handleWithdrawal}
                      className="rounded-xl font-black px-8 h-12 shadow-lg shadow-red-100 dark:shadow-none bg-red-500 hover:bg-red-600 transition-all hover:scale-[1.02] active:scale-[0.98] shrink-0"
                    >
                      탈퇴하기
                    </Button>
                  </div>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
