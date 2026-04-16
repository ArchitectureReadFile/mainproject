import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { CreditCard } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { useAuth } from '../../../features/auth'
import {
  cancelSubscription,
  subscribePremium,
} from '../../../features/auth/api/authApi'

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleDateString('ko-KR')
}

function getSubscriptionViewModel(subscription) {
  if (!subscription || subscription.plan === 'FREE') {
    return {
      planLabel: '무료 플랜',
      statusLabel: '이용 중',
      description: '기본 기능을 사용할 수 있습니다.',
      canUpgrade: true,
      canCancel: false,
    }
  }

  const { status, auto_renew, ended_at } = subscription

  if (status === 'ACTIVE') {
    return {
      planLabel: '프리미엄 플랜',
      statusLabel: auto_renew ? '이용 중' : '해지 예약',
      description: auto_renew
        ? `${formatDate(ended_at)}에 다음 프리미엄 구독이 갱신됩니다.`
        : `${formatDate(ended_at)}까지 프리미엄 기능을 사용할 수 있습니다.`,
      canUpgrade: false,
      canCancel: auto_renew,
    }
  }

  if (status === 'CANCELED') {
    return {
      planLabel: '프리미엄 플랜',
      statusLabel: '해지 예약',
      description: `${formatDate(ended_at)}까지 프리미엄 기능을 사용할 수 있습니다.`,
      canUpgrade: true,
      canCancel: false,
    }
  }

  if (status === 'EXPIRED') {
    return {
      planLabel: '무료 플랜',
      statusLabel: '프리미엄 만료',
      description: ended_at
        ? `${formatDate(ended_at)}에 프리미엄 구독이 만료되었습니다.`
        : '프리미엄 구독이 만료되었습니다.',
      canUpgrade: true,
      canCancel: false,
    }
  }

  return {
    planLabel: '무료 플랜',
    statusLabel: '상태 확인 필요',
    description: '구독 상태를 확인해주세요.',
    canUpgrade: true,
    canCancel: false,
  }
}

export default function SubscriptionSection() {
  const { user, setUser } = useAuth()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const subscription = user?.subscription ?? null
  const viewModel = useMemo(
    () => getSubscriptionViewModel(subscription),
    [subscription],
  )

  const handleSubscribe = async () => {
    setIsSubmitting(true)
    try {
      const updatedUser = await subscribePremium()
      setUser(updatedUser)
      toast.success('프리미엄 구독이 시작되었습니다.')
    } catch (error) {
      toast.error(error.message || '구독 변경에 실패했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCancel = async () => {
    setIsSubmitting(true)
    try {
      const updatedUser = await cancelSubscription()
      setUser(updatedUser)
      toast.success('자동 갱신이 해지되었습니다.')
    } catch (error) {
      toast.error(error.message || '구독 해지에 실패했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card className="border-zinc-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-none rounded-xl overflow-hidden">
      <CardHeader className="py-4 px-6 border-b border-zinc-100 dark:border-slate-900 bg-zinc-50/50 dark:bg-slate-900/50">
        <CardTitle className="text-sm font-bold flex items-center gap-2 text-zinc-700 dark:text-slate-300 uppercase tracking-tight">
          <CreditCard size={16} className="text-blue-500" /> 구독 플랜
        </CardTitle>
      </CardHeader>

      <CardContent className="p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <p className="text-lg font-black text-zinc-800 dark:text-slate-100">
                {viewModel.planLabel}
              </p>
              <Badge
                variant="outline"
                className={
                  subscription?.plan === 'PREMIUM' && subscription?.status === 'ACTIVE'
                    ? 'border-blue-500/20 text-blue-600 bg-blue-50/40 dark:bg-blue-500/10'
                    : 'border-zinc-300 text-zinc-600 bg-zinc-50 dark:bg-slate-900'
                }
              >
                {viewModel.statusLabel}
              </Badge>
            </div>

            <p className="text-sm text-zinc-500 dark:text-slate-400">
              {viewModel.description}
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              <div className="rounded-xl border border-zinc-200 dark:border-slate-800 px-4 py-3">
                <p className="text-[11px] font-bold text-zinc-400 uppercase">시작일</p>
                <p className="mt-1 text-sm font-bold text-zinc-700 dark:text-slate-200">
                  {subscription?.started_at ? formatDate(subscription.started_at) : '-'}
                </p>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-slate-800 px-4 py-3">
                <p className="text-[11px] font-bold text-zinc-400 uppercase">종료일</p>
                <p className="mt-1 text-sm font-bold text-zinc-700 dark:text-slate-200">
                  {subscription?.ended_at ? formatDate(subscription.ended_at) : '-'}
                </p>
              </div>
            </div>
          </div>

          <div className="shrink-0 flex gap-2">
            {viewModel.canUpgrade && (
              <Button
                onClick={handleSubscribe}
                disabled={isSubmitting}
                className="h-9 px-4 text-xs font-bold"
              >
                {isSubmitting ? '처리 중' : '프리미엄 시작'}
              </Button>
            )}

            {viewModel.canCancel && (
              <Button
                variant="outline"
                onClick={handleCancel}
                disabled={isSubmitting}
                className="h-9 px-4 text-xs font-bold border-zinc-200 dark:border-slate-800"
              >
                {isSubmitting ? '처리 중' : '자동 갱신 해지'}
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
