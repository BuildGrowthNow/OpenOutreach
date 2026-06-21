'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Icons } from '@/lib/types/components'
import { getCampaign, getStateMachine, simulateStateMachineExecution } from '@/lib/api/dashboard'
import { cn } from '@/lib/utils'

interface CampaignSummary {
  id: string
  name: string
}

interface StateMachineState {
  id: string
  name: string
  description?: string
}

interface StateMachineTransition {
  from: string
  to: string
  trigger: string
  description?: string
  conditions?: Record<string, unknown>[]
  actions?: Record<string, unknown>[]
}

interface StateMachineViewModel {
  startState?: string
  isActive?: boolean
  executionCount?: number
  endStates?: string[]
  states?: StateMachineState[]
  transitions?: StateMachineTransition[]
}

export default function StateMachinePage() {
  const params = useParams()
  const campaignId = params.id as string

  const [campaign, setCampaign] = useState<CampaignSummary | null>(null)
  const [stateMachine, setStateMachine] = useState<StateMachineViewModel | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('visual')
  const [simulationDialogOpen, setSimulationDialogOpen] = useState(false)
  const [simulationInput, setSimulationInput] = useState('')
  const [simulationResult, setSimulationResult] = useState<Record<string, unknown> | null>(null)
  const [simulating, setSimulating] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch campaign details
      const campaignResponse = await getCampaign(campaignId)
      if (campaignResponse.data) {
        setCampaign(campaignResponse.data!)
      } else {
        setError(campaignResponse.error || campaignResponse.message || 'Failed to fetch campaign')
      }

      // Fetch state machine
      const stateMachineResponse = await getStateMachine(campaignId)
      if (stateMachineResponse.data) {
        setStateMachine(stateMachineResponse.data as unknown as StateMachineViewModel)
      } else if (stateMachineResponse.error && !stateMachineResponse.error.includes('not found')) {
        setError(stateMachineResponse.error || 'Failed to fetch state machine')
      }
      // No state machine is okay, we'll show the empty state
    } catch (err) {
      setError('An error occurred while fetching data')
      console.error('Error fetching data:', err)
    } finally {
      setLoading(false)
    }
  }, [campaignId])

  useEffect(() => {
    void (async () => {
      await fetchData()
    })()
  }, [fetchData])

  const handleSimulate = async () => {
    if (!simulationInput.trim()) {
      setError('Please enter simulation input')
      return
    }

    try {
      setSimulating(true)
      const response = await simulateStateMachineExecution(campaignId, {
        input: simulationInput,
        startState: stateMachine?.startState || 'new',
        maxSteps: 10
      })

      if (response.data) {
        setSimulationResult(response.data)
      } else {
        setError(response.error || response.message || 'Failed to simulate')
      }
    } catch (err) {
      setError('An error occurred while simulating')
      console.error('Error simulating:', err)
    } finally {
      setSimulating(false)
    }
  }

  const refreshData = async () => {
    await fetchData()
  }

  const getStateColor = (state: string) => {
    switch (state) {
      case 'new':
        return 'border-blue-500/20 text-blue-600 dark:text-blue-400 bg-blue-500/10'
      case 'contacted':
        return 'border-purple-500/20 text-purple-600 dark:text-purple-400 bg-purple-500/10'
      case 'qualified':
        return 'border-emerald-500/20 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10'
      case 'converted':
        return 'border-orange-500/20 text-orange-600 dark:text-orange-400 bg-orange-500/10'
      case 'disqualified':
        return 'border-red-500/20 text-red-600 dark:text-red-400 bg-red-500/10'
      default:
        return 'border-gray-500/20 text-gray-600 dark:text-gray-400 bg-gray-500/10'
    }
  }

  const getStateIcon = (state: string) => {
    switch (state) {
      case 'new':
        return <Icons.CircleEllipsis className="h-4 w-4" />
      case 'contacted':
        return <Icons.MessageSquare className="h-4 w-4" />
      case 'qualified':
        return <Icons.CheckCircle className="h-4 w-4" />
      case 'converted':
        return <Icons.DollarSign className="h-4 w-4" />
      case 'disqualified':
        return <Icons.XCircle className="h-4 w-4" />
      default:
        return <Icons.Circle className="h-4 w-4" />
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
          <Skeleton className="h-10 w-32" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Skeleton className="h-64 w-full" />
          </div>
          <div className="space-y-6">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        </div>
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="space-y-6">
        <Alert variant="destructive">
          <AlertTitle>Campaign Not Found</AlertTitle>
          <AlertDescription>
            The campaign you&apos;re looking for doesn&apos;t exist or you don&apos;t have permission to view it.
          </AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => window.history.back()}>
          <Icons.ChevronLeft className="mr-2 h-4 w-4" />
          Back to Dashboard
        </Button>
      </div>
    )
  }

  const defaultStates = [
    {
      id: 'new',
      name: 'New',
      description: 'Lead has been created but not contacted yet',
      icon: getStateIcon('new'),
      color: 'bg-blue-500'
    },
    {
      id: 'contacted',
      name: 'Contacted', 
      description: 'Initial contact has been made with the lead',
      icon: getStateIcon('contacted'),
      color: 'bg-purple-500'
    },
    {
      id: 'qualified',
      name: 'Qualified',
      description: 'Lead has been qualified and is interested',
      icon: getStateIcon('qualified'),
      color: 'bg-emerald-500'
    },
    {
      id: 'converted',
      name: 'Converted',
      description: 'Lead has become a customer',
      icon: getStateIcon('converted'),
      color: 'bg-orange-500'
    },
    {
      id: 'disqualified',
      name: 'Disqualified',
      description: 'Lead is not a good fit',
      icon: getStateIcon('disqualified'),
      color: 'bg-red-500'
    }
  ]

  const defaultTransitions: Array<StateMachineTransition & { conditions?: Record<string, unknown>[], actions?: Record<string, unknown>[] }> = [
    { from: 'new', to: 'contacted', trigger: 'SEND_INITIAL_MESSAGE', description: 'Send initial contact message', conditions: [], actions: [] },
    { from: 'contacted', to: 'qualified', trigger: 'RESPONSE_RECEIVED', description: 'Lead responds positively', conditions: [], actions: [] },
    { from: 'contacted', to: 'disqualified', trigger: 'NO_RESPONSE', description: 'No response after follow-ups', conditions: [], actions: [] },
    { from: 'qualified', to: 'converted', trigger: 'MEETING_BOOKED', description: 'Book and complete meeting', conditions: [], actions: [] },
    { from: 'qualified', to: 'disqualified', trigger: 'NOT_INTERESTED', description: 'Lead decides not to proceed', conditions: [], actions: [] },
    { from: 'new', to: 'disqualified', trigger: 'INVALID_LEAD', description: 'Lead information invalid', conditions: [], actions: [] }
  ]

  const hasStateMachine = stateMachine && stateMachine.states && stateMachine.transitions

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">State Machine</h1>
          <p className="text-muted-foreground">
            Workflow automation for <span className="font-medium">{campaign.name}</span>
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={loading}
          >
            {loading ? (
              <>
                <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Refreshing...
              </>
            ) : (
              <>
                <Icons.RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </>
            )}
          </Button>
          <Dialog open={simulationDialogOpen} onOpenChange={setSimulationDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Icons.Play className="mr-2 h-4 w-4" />
                Simulate
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle>Simulate State Machine</DialogTitle>
                <DialogDescription>
                  Test how leads will move through your campaign workflow
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Simulation Input</label>
                  <textarea
                    className="w-full mt-2 p-2 border rounded-md"
                    rows={3}
                    placeholder="Enter simulation data (e.g., lead profile, response patterns)..."
                    value={simulationInput}
                    onChange={(e) => setSimulationInput(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Start State</label>
                  <select
                    className="w-full mt-2 p-2 border rounded-md"
                    value={stateMachine?.startState || 'new'}
                    onChange={() => {}}
                  >
                    {(stateMachine?.states || defaultStates).map((state) => (
                      <option key={state.id} value={state.id}>
                        {state.name}
                      </option>
                    ))}
                  </select>
                </div>
                {simulationResult && (
                  <div className="mt-4 p-4 bg-muted rounded-lg">
                    <h4 className="font-medium mb-2">Simulation Result</h4>
                    <pre className="text-sm overflow-auto max-h-40">
                      {JSON.stringify(simulationResult, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setSimulationDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleSimulate} disabled={simulating}>
                  {simulating ? (
                    <>
                      <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      Simulating...
                    </>
                  ) : (
                    <>
                      <Icons.Play className="mr-2 h-4 w-4" />
                      Run Simulation
                    </>
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button variant="outline" size="sm" onClick={() => window.history.back()}>
            <Icons.ChevronLeft className="mr-2 h-4 w-4" />
            Back to Campaign
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* State Machine Status */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">{hasStateMachine ? (stateMachine as StateMachineViewModel).states?.length ?? defaultStates.length : defaultStates.length}</div>
              <div className="text-sm text-muted-foreground">States</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{hasStateMachine ? (stateMachine as StateMachineViewModel).transitions?.length ?? defaultTransitions.length : defaultTransitions.length}</div>
              <div className="text-sm text-muted-foreground">Transitions</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{hasStateMachine ? (stateMachine.isActive ? 'Active' : 'Inactive') : 'Not Configured'}</div>
              <div className="text-sm text-muted-foreground">Status</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{hasStateMachine ? stateMachine.executionCount || 0 : 0}</div>
              <div className="text-sm text-muted-foreground">Executions</div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-3 w-full md:w-auto">
          <TabsTrigger value="visual">Visual Editor</TabsTrigger>
          <TabsTrigger value="states">States</TabsTrigger>
          <TabsTrigger value="transitions">Transitions</TabsTrigger>
        </TabsList>

        {/* Visual Editor Tab */}
        <TabsContent value="visual" className="space-y-6">
          {hasStateMachine ? (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Workflow Visualization</CardTitle>
                  <CardDescription>
                    Drag and drop states to rearrange, click to edit
                  </CardDescription>
                </CardHeader>
                 <CardContent>
                   <div className="min-h-[400px] border rounded-lg flex items-center justify-center p-8">
                     <div className="text-center">
                       <div className="inline-block p-6 bg-gray-100 dark:bg-gray-800 rounded-xl">
                         <Icons.Network className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                         <h4 className="font-medium mb-2">State Machine Visualization</h4>
                         <p className="text-sm text-muted-foreground mb-4">
                           Interactive workflow visualization for your campaign automation
                         </p>
                         <div className="flex flex-wrap gap-3 justify-center">
                           {(stateMachine.states || defaultStates).map((state) => (
                             <div
                               key={state.id}
                               className={cn(
                                 'px-4 py-2 rounded-lg border flex items-center gap-2',
                                 getStateColor(state.id)
                               )}
                             >
                               {getStateIcon(state.id)}
                               <span>{state.name}</span>
                             </div>
                           ))}
                         </div>
                         <div className="mt-6">
                           <p className="text-sm text-muted-foreground">
                             Click states to edit, drag to reposition
                           </p>
                         </div>
                       </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Quick Actions */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Button variant="outline">
                  <Icons.Plus className="mr-2 h-4 w-4" />
                  Add State
                </Button>
                <Button variant="outline">
                  <Icons.Plus className="mr-2 h-4 w-4" />
                  Add Transition
                </Button>
                <Button variant="outline">
                  <Icons.Share2 className="mr-2 h-4 w-4" />
                  Export Configuration
                </Button>
              </div>
            </>
          ) : (
            <Card>
              <CardContent className="py-12">
                <div className="text-center max-w-md mx-auto">
                  <Icons.Workflow className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No State Machine Configured</h3>
                  <p className="text-sm text-muted-foreground mb-6">
                    Create a state machine to automate lead progression through your campaign.
                    States represent lead statuses, transitions represent actions that move leads between states.
                  </p>
                  <div className="flex gap-3 justify-center">
                    <Button>
                      <Icons.Plus className="mr-2 h-4 w-4" />
                      Create State Machine
                    </Button>
                    <Button variant="outline">
                      <Icons.FileText className="mr-2 h-4 w-4" />
                      Use Template
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* States Tab */}
        <TabsContent value="states" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>States Configuration</CardTitle>
              <CardDescription>
                Define the different states a lead can be in during the campaign
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {(stateMachine?.states || defaultStates).map((state) => (
                  <div
                    key={state.id}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div className="flex items-center gap-4">
                      <div className={cn('p-2 rounded', getStateColor(state.id))}>
                        {getStateIcon(state.id)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium">{state.name}</h4>
                          {stateMachine?.startState === state.id && (
                            <Badge variant="outline" className="text-xs">
                              Start State
                            </Badge>
                          )}
                          {stateMachine?.endStates?.includes(state.id) && (
                            <Badge variant="outline" className="text-xs">
                              End State
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">{state.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm">
                        <Icons.Edit className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Icons.Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          
          <div className="flex justify-between items-center">
            <p className="text-sm text-muted-foreground">
              States define the possible statuses a lead can have in your campaign workflow
            </p>
            <Button>
              <Icons.Plus className="mr-2 h-4 w-4" />
              Add New State
            </Button>
          </div>
        </TabsContent>

        {/* Transitions Tab */}
        <TabsContent value="transitions" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Transitions</CardTitle>
              <CardDescription>
                Define how leads move between states based on events and conditions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {(stateMachine?.transitions || defaultTransitions).map((transition, index: number) => (
                  <div key={index} className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <div className={cn('px-3 py-1 rounded text-sm', getStateColor(transition.from))}>
                          {transition.from}
                        </div>
                        <Icons.ArrowRight className="h-4 w-4 text-muted-foreground" />
                        <div className={cn('px-3 py-1 rounded text-sm', getStateColor(transition.to))}>
                          {transition.to}
                        </div>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {transition.trigger}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">{transition.description}</p>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4 text-sm">
                        {transition.conditions && (
                          <div className="flex items-center gap-1">
                            <Icons.Filter className="h-3 w-3" />
                            <span>{transition.conditions.length} conditions</span>
                          </div>
                        )}
                        {transition.actions && (
                          <div className="flex items-center gap-1">
                            <Icons.Zap className="h-3 w-3" />
                            <span>{transition.actions.length} actions</span>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm">
                          <Icons.Edit className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm">
                          <Icons.Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Transition Builder */}
          <Card>
            <CardHeader>
              <CardTitle>Create New Transition</CardTitle>
              <CardDescription>
                Define a new way for leads to move between states
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">From State</label>
                    <select className="w-full mt-1 p-2 border rounded-md">
                      {(stateMachine?.states || defaultStates).map((state) => (
                        <option key={state.id} value={state.id}>
                          {state.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-medium">To State</label>
                    <select className="w-full mt-1 p-2 border rounded-md">
                      {(stateMachine?.states || defaultStates).map((state) => (
                        <option key={state.id} value={state.id}>
                          {state.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">Trigger Event</label>
                    <input className="w-full mt-1 p-2 border rounded-md" placeholder="e.g., RESPONSE_RECEIVED" />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Description</label>
                    <textarea className="w-full mt-1 p-2 border rounded-md" rows={2} placeholder="Describe what triggers this transition..." />
                  </div>
                </div>
              </div>
              <div className="mt-6 flex justify-end">
                <Button>
                  <Icons.Plus className="mr-2 h-4 w-4" />
                  Add Transition
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* State Machine Features */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Automated Actions</CardTitle>
            <CardDescription>Configure automatic responses</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              <li className="flex items-center gap-2">
                <Icons.Check className="h-4 w-4 text-emerald-500" />
                <span className="text-sm">Auto-send welcome message</span>
              </li>
              <li className="flex items-center gap-2">
                <Icons.Check className="h-4 w-4 text-emerald-500" />
                <span className="text-sm">Follow-up reminders</span>
              </li>
              <li className="flex items-center gap-2">
                <Icons.Check className="h-4 w-4 text-emerald-500" />
                <span className="text-sm">Lead scoring updates</span>
              </li>
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Conditions & Rules</CardTitle>
            <CardDescription>Custom logic for transitions</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              <li className="flex items-center gap-2">
                <Icons.Filter className="h-4 w-4 text-blue-500" />
                <span className="text-sm">Time-based conditions</span>
              </li>
              <li className="flex items-center gap-2">
                <Icons.Filter className="h-4 w-4 text-blue-500" />
                <span className="text-sm">Lead score thresholds</span>
              </li>
              <li className="flex items-center gap-2">
                <Icons.Filter className="h-4 w-4 text-blue-500" />
                <span className="text-sm">Response content analysis</span>
              </li>
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Analytics & Insights</CardTitle>
            <CardDescription>Track workflow performance</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              <li className="flex items-center gap-2">
                <Icons.BarChart3 className="h-4 w-4 text-purple-500" />
                <span className="text-sm">Transition frequency</span>
              </li>
              <li className="flex items-center gap-2">
                <Icons.BarChart3 className="h-4 w-4 text-purple-500" />
                <span className="text-sm">Time in each state</span>
              </li>
              <li className="flex items-center gap-2">
                <Icons.BarChart3 className="h-4 w-4 text-purple-500" />
                <span className="text-sm">Conversion bottlenecks</span>
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
