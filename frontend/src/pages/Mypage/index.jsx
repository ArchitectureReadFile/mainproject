import { Button } from '@/components/ui/Button'
import { Tabs, TabsContent } from '@/components/ui/Tabs'
import { cn } from '@/lib/utils'
import { Bell, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import EmailSection from './components/EmailSection'
import NotificationSection from './components/NotificationSection'
import ProfileSection from './components/ProfileSection'
import SecuritySection from './components/SecuritySection'

export default function Mypage() {
  const [activeTab, setActiveTab] = useState("account")

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
    <div className="flex flex-col md:flex-row gap-12 items-start">
        <div className="w-full md:w-64 space-y-1 shrink-0">
          <Button 
            variant="ghost" 
            onClick={() => setActiveTab("account")}
            className={cn(
              "w-full justify-start gap-3 rounded-xl font-bold h-11 transition-all",
              activeTab === "account" ? "text-blue-500 bg-blue-50/50 dark:bg-blue-900/20" : "text-zinc-500 hover:bg-zinc-50 dark:hover:bg-zinc-900"
            )}
          >
            <ShieldCheck size={18} /> 계정 및 보안
          </Button>
          <Button 
            variant="ghost" 
            onClick={() => setActiveTab("notification")}
            className={cn(
              "w-full justify-start gap-3 rounded-xl font-bold h-11 transition-all",
              activeTab === "notification" ? "text-blue-500 bg-blue-50/50 dark:bg-blue-900/20" : "text-zinc-500 hover:bg-zinc-50 dark:hover:bg-zinc-900"
            )}
          >
            <Bell size={18} /> 알림 설정
          </Button>
        </div>

        <div className="flex-1 w-full">
          <Tabs value={activeTab} className="w-full">
            <TabsContent value="account" className="mt-0 space-y-16 animate-in fade-in duration-300">
              <div className="space-y-6">
                <div className="relative flex items-center justify-center">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t border-zinc-200 dark:border-zinc-800" />
                  </div>
                  <span className="relative bg-white dark:bg-zinc-950 px-4 text-[11px] font-black text-zinc-400 dark:text-zinc-500 uppercase tracking-[0.3em]">
                    일반 설정
                  </span>
                </div>
                
                <ProfileSection />
                <EmailSection />
                <SecuritySection />
              </div>
            </TabsContent>
            
            <TabsContent value="notification" className="mt-0 animate-in fade-in duration-300">
              <NotificationSection />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}