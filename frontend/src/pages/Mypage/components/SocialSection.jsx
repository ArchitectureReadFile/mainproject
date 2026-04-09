import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { LinkIcon } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../../../features/auth'
import { unlinkSocialAccount } from '../../../features/auth/api/authApi'

export default function SocialSection() {
  const { user, setUser } = useAuth()
  const [isUnlinking, setIsUnlinking] = useState('')
  const [searchParams, setSearchParams] = useSearchParams()
  const [localErrors, setLocalErrors] = useState({})

  useEffect(() => {
    const errorMsg = searchParams.get('social_error')
    const provider = searchParams.get('provider')
    
    if (errorMsg && provider) {
      setLocalErrors(prev => ({ ...prev, [provider]: decodeURIComponent(errorMsg) }))
      
      const newParams = new URLSearchParams(searchParams)
      newParams.delete('social_error')
      newParams.delete('provider')
      setSearchParams(newParams, { replace: true })
    }
  }, [searchParams, setSearchParams])

  const handleUnlink = async (provider) => {
    setIsUnlinking(provider)
    setLocalErrors(prev => ({ ...prev, [provider]: '' }))
    try {
      await unlinkSocialAccount(provider)
      setUser(prev => ({
        ...prev,
        social_providers: prev.social_providers.filter(p => p !== provider)
      }))
    } catch (error) {
      console.error("soscial unlink error", error)
    } finally {
      setIsUnlinking('')
    }
  }

  const handleLink = (provider) => {
    setLocalErrors(prev => ({ ...prev, [provider]: '' }))
    window.location.href = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/auth/social/${provider}/login`
  }

  const isGoogleLinked = user?.social_providers?.includes('google')
  const isGithubLinked = user?.social_providers?.includes('github')

  return (
    <Card className="border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-none rounded-xl overflow-hidden mt-6">
      <CardHeader className="py-3 px-5 border-b border-zinc-100 dark:border-zinc-900 bg-zinc-50/50 dark:bg-zinc-900/50">
        <CardTitle className="text-sm font-bold flex items-center gap-3 text-zinc-700 dark:text-zinc-300 uppercase tracking-tight">
          <div className="w-7 h-7 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center shrink-0">
            <LinkIcon size={14} className="text-zinc-600 dark:text-zinc-400" />
          </div>
          소셜 연동
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5 space-y-4">
        <div className="flex flex-col py-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-white border shadow-sm flex items-center justify-center shrink-0">
                <svg width="18" height="18" viewBox="0 0 18 18">
                  <path d="M17.64 9.2c0-.63-.06-1.25-.16-1.84H9v3.49h4.84a4.14 4.14 0 0 1-1.8 2.71v2.26h2.91c1.71-1.58 2.69-3.9 2.69-6.62z" fill="#4285F4"/>
                  <path d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.91-2.26c-.8.54-1.83.85-3.05.85-2.34 0-4.32-1.58-5.03-3.71H.95v2.3A8.99 8.99 0 0 0 9 18z" fill="#34A853"/>
                  <path d="M3.97 10.71A5.41 5.41 0 0 1 3.68 9c0-.59.1-1.17.29-1.71V4.99H.95A8.99 8.99 0 0 0 0 9c0 1.45.35 2.82.95 4.01l3.02-2.3z" fill="#FBBC05"/>
                  <path d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0 5.48 0 2.39 2.02.95 4.99l3.02 2.3c.71-2.13 2.69-3.71 5.03-3.71z" fill="#EA4335"/>
                </svg>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-bold text-zinc-800 dark:text-zinc-200">Google</p>
                <p className="text-[11px] font-medium text-zinc-500">
                  {isGoogleLinked ? 'Google 계정과 연동되어 있습니다.' : 'Google 계정을 연동하여 간편하게 로그인하세요.'}
                </p>
              </div>
            </div>
            <Button
              variant={isGoogleLinked ? 'outline' : 'default'}
              onClick={() => isGoogleLinked ? handleUnlink('google') : handleLink('google')}
              disabled={isUnlinking === 'google'}
              className="h-8 px-4 text-xs font-bold"
            >
              {isUnlinking === 'google' ? '처리 중' : isGoogleLinked ? '연동 해제' : '연동하기'}
            </Button>
          </div>
          {localErrors['google'] && (
            <p className="text-xs font-bold text-red-500 mt-2 ml-11">{localErrors['google']}</p>
          )}
        </div>

        <div className="h-px bg-zinc-100 dark:bg-zinc-800/50" />

        <div className="flex flex-col py-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-white border shadow-sm flex items-center justify-center shrink-0">
                <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                </svg>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-bold text-zinc-800 dark:text-zinc-200">GitHub</p>
                <p className="text-[11px] font-medium text-zinc-500">
                  {isGithubLinked ? 'GitHub 계정과 연동되어 있습니다.' : 'GitHub 계정을 연동하여 간편하게 로그인하세요.'}
                </p>
              </div>
            </div>
            <Button
              variant={isGithubLinked ? 'outline' : 'default'}
              onClick={() => isGithubLinked ? handleUnlink('github') : handleLink('github')}
              disabled={isUnlinking === 'github'}
              className="h-8 px-4 text-xs font-bold"
            >
              {isUnlinking === 'github' ? '처리 중' : isGithubLinked ? '연동 해제' : '연동하기'}
            </Button>
          </div>
          {localErrors['github'] && (
            <p className="text-xs font-bold text-red-500 mt-2 ml-11">{localErrors['github']}</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}