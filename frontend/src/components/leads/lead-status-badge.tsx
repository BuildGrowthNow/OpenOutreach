'use client'

import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { DealState, DealOutcome } from '@/lib/types/components'

interface LeadStatusBadgeProps {
  state: DealState
  outcome?: DealOutcome
  className?: string
}

const stateConfig: Record<DealState, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; color: string }> = {
  QUALIFIED: {
    label: 'Qualified',
    variant: 'outline',
    color: 'text-blue-600 border-blue-600'
  },
  READY_TO_CONNECT: {
    label: 'Ready to Connect',
    variant: 'outline',
    color: 'text-emerald-600 border-emerald-600'
  },
  PENDING: {
    label: 'Pending',
    variant: 'outline',
    color: 'text-amber-600 border-amber-600'
  },
  CONNECTED: {
    label: 'Connected',
    variant: 'outline',
    color: 'text-purple-600 border-purple-600'
  },
  COMPLETED: {
    label: 'Completed',
    variant: 'outline',
    color: 'text-green-600 border-green-600'
  },
  FAILED: {
    label: 'Failed',
    variant: 'destructive',
    color: 'text-red-600 border-red-600'
  },
  NO_EMAIL: {
    label: 'No Email',
    variant: 'secondary',
    color: 'text-gray-600 border-gray-600'
  }
}

const outcomeConfig: Record<DealOutcome, { label: string; color: string }> = {
  not_interested: {
    label: 'Not Interested',
    color: 'text-amber-600'
  },
  interested: {
    label: 'Interested',
    color: 'text-emerald-600'
  },
  scheduled: {
    label: 'Scheduled',
    color: 'text-blue-600'
  },
  wrong_person: {
    label: 'Wrong Person',
    color: 'text-red-600'
  },
  no_response: {
    label: 'No Response',
    color: 'text-gray-600'
  },
  other: {
    label: 'Other',
    color: 'text-slate-600'
  }
}

export function LeadStatusBadge({ state, outcome, className }: LeadStatusBadgeProps) {
  const stateInfo = stateConfig[state]
  const outcomeInfo = outcome ? outcomeConfig[outcome] : null

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <Badge variant={stateInfo.variant} className={cn('w-fit text-xs', stateInfo.color)}>
        {stateInfo.label}
      </Badge>
      {outcomeInfo && (
        <div className={cn('text-xs font-medium', outcomeInfo.color)}>
          {outcomeInfo.label}
        </div>
      )}
    </div>
  )
}