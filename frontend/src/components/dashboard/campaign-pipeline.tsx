'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'

interface CampaignPipelineProps {
  qualified: number
  readyToConnect: number
  pending: number
  connected: number
  completed: number
  failed: number
  noEmail: number
}

interface StageConfig {
  color: string
  textColor: string
}

const stateConfig: Record<string, StageConfig> = {
  qualified: {
    color: 'bg-blue-500',
    textColor: 'text-blue-600 dark:text-blue-400',
  },
  readyToConnect: {
    color: 'bg-indigo-500',
    textColor: 'text-indigo-600 dark:text-indigo-400',
  },
  pending: {
    color: 'bg-purple-500',
    textColor: 'text-purple-600 dark:text-purple-400',
  },
  connected: {
    color: 'bg-cyan-500',
    textColor: 'text-cyan-600 dark:text-cyan-400',
  },
  completed: {
    color: 'bg-emerald-500',
    textColor: 'text-emerald-600 dark:text-emerald-400',
  },
  failed: {
    color: 'bg-red-500',
    textColor: 'text-red-600 dark:text-red-400',
  },
  noEmail: {
    color: 'bg-gray-500',
    textColor: 'text-gray-600 dark:text-gray-400',
  },
}

interface PipelineStage {
  label: string
  value: number
  color: string
  textColor: string
}

const CampaignPipeline = ({
  qualified,
  readyToConnect,
  pending,
  connected,
  completed,
  failed,
  noEmail,
}: CampaignPipelineProps) => {
  const stages: PipelineStage[] = [
    { label: 'Qualified', value: qualified, ...stateConfig.qualified },
    { label: 'Ready to Connect', value: readyToConnect, ...stateConfig.readyToConnect },
    { label: 'Pending', value: pending, ...stateConfig.pending },
    { label: 'Connected', value: connected, ...stateConfig.connected },
    { label: 'Completed', value: completed, ...stateConfig.completed },
    { label: 'Failed', value: failed, ...stateConfig.failed },
    { label: 'No Email', value: noEmail, ...stateConfig.noEmail },
  ]

  const total = stages.reduce((sum, stage) => sum + stage.value, 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Campaign Pipeline</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {stages.map((stage) => (
            <div key={stage.label} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div className={`h-2.5 w-2.5 rounded-full ${stage.color}`} />
                  <span className="font-medium text-foreground">{stage.label}</span>
                  <span className="text-muted-foreground">({stage.value})</span>
                </div>
                {total > 0 && (
                  <span className="text-muted-foreground">
                    {((stage.value / total) * 100).toFixed(1)}%
                  </span>
                )}
              </div>
              <Progress value={(stage.value / total) * 100} className="h-2" />
            </div>
          ))}
        </div>

        <div className="mt-6 pt-4 border-t">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Total Leads</span>
            <span className="text-lg font-bold">{total}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export { CampaignPipeline }