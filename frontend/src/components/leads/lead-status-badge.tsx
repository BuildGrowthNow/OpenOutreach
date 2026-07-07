'use client'

import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { DealState, DealOutcome } from '@/lib/types/components'

interface LeadStatusBadgeProps {
  state: DealState
  outcome?: DealOutcome
  className?: string
}

// Map to normalize state from backend format (Title Case with spaces) to frontend format
const normalizeState = (state: string): DealState => {
  const stateMap: Record<string, DealState> = {
    'Qualified': 'QUALIFIED',
    'Ready to Connect': 'READY_TO_CONNECT',
    'Pending': 'PENDING',
    'Connected': 'CONNECTED',
    'Completed': 'COMPLETED',
    'Failed': 'FAILED',
    'No Email': 'NO_EMAIL',
  }
  return (stateMap[state] || state) as DealState
}

const stateConfig: Record<DealState, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; color: string }> = {
  DISCOVERED: {
    label: 'Discovered',
    variant: 'outline',
    color: 'text-slate-600 border-slate-600'
  },
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

// Default config for unknown states
const defaultStateConfig = {
  label: 'Unknown',
  variant: 'secondary' as const,
  color: 'text-gray-600 border-gray-600'
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
  // Normalize state value from backend format to frontend format
  const normalizedState = normalizeState(state as string)
  const stateInfo = stateConfig[normalizedState] || defaultStateConfig
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
