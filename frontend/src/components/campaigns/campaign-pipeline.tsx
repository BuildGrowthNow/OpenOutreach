'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'

interface PipelineStage {
  id: string
  name: string
  count: number
  percentage: number
  description: string
  color: string
  icon: React.ReactNode
}

interface Deal {
  id: string
  name: string
  company: string
  value: number
  stage: string
  status: 'active' | 'won' | 'lost' | 'pending'
  lastActivity: string
  probability: number
}

interface CampaignPipelineProps {
  stages?: PipelineStage[]
  deals?: Deal[]
  className?: string
}

export function CampaignPipeline({ stages, deals, className }: CampaignPipelineProps) {
  const defaultStages: PipelineStage[] = [
    {
      id: 'new',
      name: 'New Leads',
      count: 24,
      percentage: 20,
      description: 'Recently added leads',
      color: 'bg-blue-500',
      icon: <Icons.CircleEllipsis className="h-4 w-4" />
    },
    {
      id: 'contacted',
      name: 'Contacted',
      count: 18,
      percentage: 15,
      description: 'Initial contact made',
      color: 'bg-blue-400',
      icon: <Icons.MessageSquare className="h-4 w-4" />
    },
    {
      id: 'qualified',
      name: 'Qualified',
      count: 12,
      percentage: 10,
      description: 'Leads qualified',
      color: 'bg-purple-500',
      icon: <Icons.CheckCircle className="h-4 w-4" />
    },
    {
      id: 'proposal',
      name: 'Proposal Sent',
      count: 8,
      percentage: 6.7,
      description: 'Proposals delivered',
      color: 'bg-orange-500',
      icon: <Icons.FileText className="h-4 w-4" />
    },
    {
      id: 'negotiation',
      name: 'Negotiation',
      count: 5,
      percentage: 4.2,
      description: 'In negotiation',
      color: 'bg-yellow-500',
      icon: <Icons.Handshake className="h-4 w-4" />
    },
    {
      id: 'closed',
      name: 'Closed Won',
      count: 3,
      percentage: 2.5,
      description: 'Deals won',
      color: 'bg-emerald-500',
      icon: <Icons.Trophy className="h-4 w-4" />
    }
  ]

  const defaultDeals: Deal[] = [
    {
      id: '1',
      name: 'John Smith',
      company: 'TechCorp Inc.',
      value: 25000,
      stage: 'qualified',
      status: 'active',
      lastActivity: '2 days ago',
      probability: 75
    },
    {
      id: '2',
      name: 'Sarah Johnson',
      company: 'Digital Solutions',
      value: 45000,
      stage: 'proposal',
      status: 'active',
      lastActivity: '1 day ago',
      probability: 60
    },
    {
      id: '3',
      name: 'Michael Chen',
      company: 'InnovateSoft',
      value: 32000,
      stage: 'negotiation',
      status: 'active',
      lastActivity: 'Today',
      probability: 85
    },
    {
      id: '4',
      name: 'Emma Wilson',
      company: 'NextGen Tech',
      value: 29000,
      stage: 'contacted',
      status: 'active',
      lastActivity: '3 days ago',
      probability: 40
    },
    {
      id: '5',
      name: 'Robert Davis',
      company: 'Cloud Systems',
      value: 58000,
      stage: 'closed',
      status: 'won',
      lastActivity: '1 week ago',
      probability: 100
    }
  ]

  const pipelineStages = stages || defaultStages
  const pipelineDeals = deals || defaultDeals

  const getStageColor = (stageId: string) => {
    switch (stageId) {
      case 'new':
        return 'border-blue-500/20 text-blue-600 dark:text-blue-400 bg-blue-500/10'
      case 'contacted':
        return 'border-blue-400/20 text-blue-500 dark:text-blue-300 bg-blue-400/10'
      case 'qualified':
        return 'border-purple-500/20 text-purple-600 dark:text-purple-400 bg-purple-500/10'
      case 'proposal':
        return 'border-orange-500/20 text-orange-600 dark:text-orange-400 bg-orange-500/10'
      case 'negotiation':
        return 'border-yellow-500/20 text-yellow-600 dark:text-yellow-400 bg-yellow-500/10'
      case 'closed':
        return 'border-emerald-500/20 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10'
      default:
        return 'border-gray-500/20 text-gray-600 dark:text-gray-400 bg-gray-500/10'
    }
  }

  const getStatusColor = (status: Deal['status']) => {
    switch (status) {
      case 'active':
        return 'border-blue-500/20 text-blue-600 dark:text-blue-400 bg-blue-500/10'
      case 'won':
        return 'border-emerald-500/20 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10'
      case 'lost':
        return 'border-red-500/20 text-red-600 dark:text-red-400 bg-red-500/10'
      case 'pending':
        return 'border-amber-500/20 text-amber-600 dark:text-amber-400 bg-amber-500/10'
      default:
        return 'border-gray-500/20 text-gray-600 dark:text-gray-400 bg-gray-500/10'
    }
  }

  const totalDeals = pipelineDeals.length
  const totalValue = pipelineDeals.reduce((sum, deal) => sum + deal.value, 0)
  const averageProbability = pipelineDeals.reduce((sum, deal) => sum + deal.probability, 0) / totalDeals

  return (
    <div className={cn('space-y-6', className)}>
      {/* Pipeline Overview */}
      <Card>
        <CardHeader>
          <CardTitle>Sales Pipeline</CardTitle>
          <CardDescription>Visual representation of your sales funnel</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Pipeline Stages */}
          <div className="relative mb-8">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm text-muted-foreground">
                {totalDeals} deals in pipeline • ${totalValue.toLocaleString()} total value
              </div>
              <div className="text-sm font-medium">
                Avg Probability: {Math.round(averageProbability)}%
              </div>
            </div>

            {/* Pipeline Visualization */}
            <div className="relative">
              {/* Connecting Line */}
              <div className="absolute top-1/2 left-4 right-4 h-0.5 bg-gray-200 dark:bg-gray-700 -translate-y-1/2 z-0" />

              {/* Stages */}
              <div className="relative flex justify-between z-10">
                {pipelineStages.map((stage, index) => (
                  <div key={stage.id} className="flex flex-col items-center text-center">
                    {/* Stage Node */}
                    <div className={cn(
                      'w-16 h-16 rounded-full flex items-center justify-center mb-3 border-4 relative',
                      stage.color,
                      'bg-white dark:bg-gray-800'
                    )}>
                      <div className={cn('w-12 h-12 rounded-full flex items-center justify-center', stage.color)}>
                        {stage.icon}
                      </div>
                      {/* Count Badge */}
                      <div className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-white dark:bg-gray-800 border flex items-center justify-center">
                        <span className="text-xs font-bold">{stage.count}</span>
                      </div>
                    </div>

                    {/* Stage Info */}
                    <h4 className="font-medium text-sm mb-1">{stage.name}</h4>
                    <p className="text-xs text-muted-foreground">{stage.description}</p>
                    <div className="text-xs font-medium mt-1">{stage.percentage}%</div>

                    {/* Stage Percentage Bar */}
                    <div className="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full mt-2">
                      <div
                        className={cn('h-2 rounded-full', stage.color)}
                        style={{ width: `${stage.percentage}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Deal List */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Deals</CardTitle>
          <CardDescription>Active deals in your pipeline</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {pipelineDeals.slice(0, 5).map(deal => (
              <div
                key={deal.id}
                className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                <div className="flex items-center gap-4 flex-1">
                  <div className="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                    <span className="font-semibold text-blue-600 dark:text-blue-400">
                      ${(deal.value / 1000).toFixed(0)}k
                    </span>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium">{deal.name}</h4>
                      <Badge variant="outline" className={cn('text-xs', getStatusColor(deal.status))}>
                        {deal.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{deal.company}</p>
                    <div className="flex items-center gap-4 mt-1">
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Icons.Calendar className="h-3 w-3" />
                        {deal.lastActivity}
                      </span>
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Icons.TrendingUp className="h-3 w-3" />
                        {deal.probability}% probability
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className={cn('text-xs', getStageColor(deal.stage))}>
                    {pipelineStages.find(s => s.id === deal.stage)?.name || deal.stage}
                  </Badge>
                  <Button variant="ghost" size="sm">
                    <Icons.ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}

            {pipelineDeals.length === 0 && (
              <div className="text-center py-8">
                <Icons.Briefcase className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h4 className="text-lg font-semibold mb-2">No Deals Yet</h4>
                <p className="text-sm text-muted-foreground max-w-md mx-auto mb-6">
                  Start moving leads through your pipeline to see deals appear here.
                </p>
                <Button variant="outline">
                  <Icons.Plus className="mr-2 h-4 w-4" />
                  Add New Deal
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Pipeline Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Conversion Rate</CardTitle>
            <CardDescription>Pipeline efficiency</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-3xl font-bold">
                {pipelineStages[pipelineStages.length - 1]?.percentage || 2.5}%
              </div>
              <p className="text-sm text-muted-foreground">
                Overall conversion from lead to closed won
              </p>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mt-2">
                <div
                  className="bg-emerald-500 h-2 rounded-full"
                  style={{ width: `${pipelineStages[pipelineStages.length - 1]?.percentage || 2.5}%` }}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Average Deal Size</CardTitle>
            <CardDescription>Value per deal</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-3xl font-bold">
                ${totalDeals > 0 ? Math.round(totalValue / totalDeals).toLocaleString() : '0'}
              </div>
              <p className="text-sm text-muted-foreground">
                Average value of deals in pipeline
              </p>
              <div className="flex items-center gap-2 mt-2">
                <Icons.TrendingUp className="h-4 w-4 text-emerald-500" />
                <span className="text-sm text-emerald-600 dark:text-emerald-400">
                  +12% from last month
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Pipeline Velocity</CardTitle>
            <CardDescription>Speed of movement</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-3xl font-bold">24 days</div>
              <p className="text-sm text-muted-foreground">
                Average time from new lead to closed won
              </p>
              <div className="flex items-center gap-2 mt-2">
                <Icons.TrendingDown className="h-4 w-4 text-amber-500" />
                <span className="text-sm text-amber-600 dark:text-amber-400">
                  -3 days from last month
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Stage Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Stage Breakdown</CardTitle>
          <CardDescription>Detailed analysis of each pipeline stage</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {pipelineStages.map(stage => (
              <div key={stage.id} className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn('w-3 h-3 rounded-full', stage.color)} />
                    <div>
                      <h4 className="font-medium">{stage.name}</h4>
                      <p className="text-sm text-muted-foreground">{stage.description}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium">{stage.count} deals</div>
                    <div className="text-sm text-muted-foreground">{stage.percentage}% of pipeline</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-3/4">
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                      <div
                        className={cn('h-2 rounded-full', stage.color)}
                        style={{ width: `${stage.percentage}%` }}
                      />
                    </div>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Conversion to next stage: {Math.round(stage.percentage * 0.8)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}