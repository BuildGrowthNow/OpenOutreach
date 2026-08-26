'use client'

import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { DealState, DealOutcome } from '@/lib/types/components'
import { AlertCircle } from 'lucide-react'

interface LeadStatusBadgeProps {
  state: DealState
  outcome?: DealOutcome
  connectAttempts?: number
  qualificationHold?: boolean
  qualificationReason?: string
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
    // email states arrive from backend as lowercase snake_case
    'email_queued': 'EMAIL_QUEUED',
    'email_sent': 'EMAIL_SENT',
    'email_opened': 'EMAIL_OPENED',
    'email_replied': 'EMAIL_REPLIED',
    'email_bounced': 'EMAIL_BOUNCED',
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
  },
  EMAIL_QUEUED: {
    label: 'Email Queued',
    variant: 'outline',
    color: 'text-sky-600 border-sky-600'
  },
  EMAIL_SENT: {
    label: 'Email Sent',
    variant: 'outline',
    color: 'text-blue-600 border-blue-600'
  },
  EMAIL_OPENED: {
    label: 'Email Opened',
    variant: 'outline',
    color: 'text-violet-600 border-violet-600'
  },
  EMAIL_REPLIED: {
    label: 'Email Replied',
    variant: 'outline',
    color: 'text-emerald-600 border-emerald-600'
  },
  EMAIL_BOUNCED: {
    label: 'Email Bounced',
    variant: 'destructive',
    color: 'text-red-600 border-red-600'
  }
}

// Default config for unknown states
const defaultStateConfig = {
  label: 'Unknown',
  variant: 'secondary' as const,
  color: 'text-gray-600 border-gray-600'
}

const outcomeConfig: Record<DealOutcome, { label: string; color: string }> = {
  converted: {
    label: 'Converted',
    color: 'text-emerald-600'
  },
  not_interested: {
    label: 'Not Interested',
    color: 'text-amber-600'
  },
  wrong_fit: {
    label: 'Wrong Fit',
    color: 'text-red-600'
  },
  no_budget: {
    label: 'No Budget',
    color: 'text-orange-600'
  },
  has_solution: {
    label: 'Has Solution',
    color: 'text-slate-600'
  },
  bad_timing: {
    label: 'Bad Timing',
    color: 'text-blue-600'
  },
  unresponsive: {
    label: 'Unresponsive',
    color: 'text-gray-500'
  },
  unknown: {
    label: 'Unknown',
    color: 'text-gray-400'
  }
}

export function LeadStatusBadge({ state, outcome, connectAttempts, qualificationHold, qualificationReason, className }: LeadStatusBadgeProps) {
  // Normalize state value from backend format to frontend format
  const normalizedState = normalizeState(state as string)
  const stateInfo = stateConfig[normalizedState] || defaultStateConfig
  const outcomeInfo = outcome ? outcomeConfig[outcome] : null

  // Show retry attempts for QUALIFIED leads that are being retried
  const showRetry = normalizedState === 'QUALIFIED' && connectAttempts && connectAttempts > 0;
  // Show "Needs Review" for DISCOVERED leads held by AI qualification
  const showHold = normalizedState === 'DISCOVERED' && qualificationHold === true;

  // NO_EMAIL state needs explanation
  if (normalizedState === 'NO_EMAIL') {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className={cn('flex flex-col gap-1', className)}>
              <Badge variant={stateInfo.variant} className={cn('w-fit text-xs gap-1', stateInfo.color)}>
                <AlertCircle className="h-3 w-3" />
                {stateInfo.label}
              </Badge>
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-xs">
            <p className="text-sm">
              Email enrichment found no work email for this lead. Add manually to proceed with outreach.
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <Badge variant={stateInfo.variant} className={cn('w-fit text-xs', stateInfo.color)}>
        {stateInfo.label}
      </Badge>
      {showHold && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="outline" className="w-fit text-xs gap-1 text-yellow-600 border-yellow-600">
                <AlertCircle className="h-3 w-3" />
                Needs Review
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-sm">
                {qualificationReason
                  ? `AI held for review: ${qualificationReason}`
                  : 'AI could not confidently qualify or reject this lead. Manual review required.'}
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
      {showRetry && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="outline" className="w-fit text-xs gap-1 text-amber-600 border-amber-600">
                <AlertCircle className="h-3 w-3" />
                Retry {connectAttempts}/3
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-sm">
                Profile unreachable (no Connect button found). Retrying automatically.
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
      {outcomeInfo && (
        <div className={cn('text-xs font-medium', outcomeInfo.color)}>
          {outcomeInfo.label}
        </div>
      )}
    </div>
  )
}
