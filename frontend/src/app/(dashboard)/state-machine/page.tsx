'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/lib/types/components'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { getCampaigns, getStateMachine, updateStateMachine, validateStateMachine, simulateStateMachine } from '@/lib/api/dashboard'
import { Canvas } from '@/components/state-machine'

import type { Node as CanvasNode, Edge as CanvasEdge } from '@/components/state-machine/canvas'

interface StateMachineData {
  id: string | null
  campaign_id: string
  name: string
  description: string
  is_active: boolean
  is_valid: boolean
  validation_errors: string[]
  nodes: (CanvasNode & { id: string; type: string; config?: Record<string, unknown> })[]
  transitions: { id: string; source_node: string; target_node: string; label?: string; condition_type?: string }[]
}

interface Campaign {
  id: string
  name: string
}

const StateMachinePage = () => {
  const router = useRouter()
  const params = useParams()
  const campaignId = params.id as string

  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [campaignsLoading, setCampaignsLoading] = useState(false)
  
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>(campaignId || '')
  const [stateMachine, setStateMachine] = useState<StateMachineData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Validation
  const [validationResult, setValidationResult] = useState<{
    is_valid: boolean
    errors: string[]
    warnings: string[]
  } | null>(null)
  const [validating, setValidating] = useState(false)

  // Simulation
  const [simulationResult, setSimulationResult] = useState<{
    success: boolean
    simulation: {
      path: Array<{
        node: string
        name: string
        type: string
      }>
      nodes_visited: number
      transitions_used: number
      final_status: string
      messages_sent: string[]
      completed: boolean
      steps: number
      error: string | null
    }
  } | null>(null)
  const [simulating, setSimulating] = useState(false)
  const [simulationDeals, setSimulationDeals] = useState<string[]>([])
  const [selectedSimulationDeal, setSelectedSimulationDeal] = useState<string>('')

  // Node editing
  const [editingNode, setEditingNode] = useState<CanvasNode | null>(null)
  const [nodeEditorOpen, setNodeEditorOpen] = useState(false)

  // New node creation
  const [newNodeOpen, setNewNodeOpen] = useState(false)
  const [newNodeType, setNewNodeType] = useState<CanvasNode['type']>('state')

  // Canvas state
  const [canvasNodes, setCanvasNodes] = useState<CanvasNode[]>([])
  const [canvasEdges, setCanvasEdges] = useState<CanvasEdge[]>([])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  // Fetch campaigns
  const fetchCampaigns = useCallback(async () => {
    try {
      setCampaignsLoading(true)
      const response = await getCampaigns()
      if (response.data) {
        setCampaigns(response.data.data || [])
        if (!selectedCampaignId && response.data.data.length > 0) {
          setSelectedCampaignId(response.data.data[0].id)
        }
      }
    } catch (err) {
      console.error('Error fetching campaigns:', err)
    } finally {
      setCampaignsLoading(false)
    }
  }, [selectedCampaignId])

  // Fetch state machine
  const fetchStateMachine = useCallback(async (id: string) => {
    try {
      setLoading(true)
      setError(null)
      const response = await getStateMachine(id)
      
      if (response.data) {
        // Map to canvas format first
        const nodes: CanvasNode[] = (response.data.nodes || []).map(n => ({
          id: n.id,
          type: n.type as CanvasNode['type'] || 'state',
          name: n.name,
          description: n.description,
          x: n.x || 100,
          y: n.y || 100,
          width: 220,
          height: 80
        }))
        
        const edges: CanvasEdge[] = (response.data.transitions || []).map(t => ({
          id: t.id,
          sourceId: t.source_node,
          targetId: t.target_node,
          trigger: t.label || ''
        }))
        
        setCanvasNodes(nodes)
        setCanvasEdges(edges)
        
        // Create StateMachineData from response
        const stateMachineData: StateMachineData = {
          id: response.data.id,
          campaign_id: response.data.campaign_id,
          name: response.data.name,
          description: response.data.description,
          is_active: response.data.is_active,
          is_valid: response.data.is_valid,
          validation_errors: response.data.validation_errors,
          nodes: nodes.map(n => ({
            id: n.id,
            type: n.type,
            name: n.name,
            description: n.description,
            x: n.x,
            y: n.y,
            config: {},
            width: n.width,
            height: n.height
          })),
          transitions: (response.data.transitions || []).map(t => ({
            id: t.id,
            source_node: t.source_node,
            target_node: t.target_node,
            label: t.label,
            condition_type: t.condition_type
          }))
        }
        
        setStateMachine(stateMachineData)
      } else {
        setError(response.error || 'Failed to fetch state machine')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch state machine')
    } finally {
      setLoading(false)
    }
  }, [])

  // Handle campaign change
  const handleCampaignChange = useCallback(async (value: string) => {
    setSelectedCampaignId(value)
    setValidationResult(null)
    setSimulationResult(null)
    setEditingNode(null)
    setCanvasNodes([])
    setCanvasEdges([])
  }, [])

  // Handle node click
  const handleNodeClick = useCallback((nodeId: string) => {
    if (!stateMachine?.nodes) return
    const node = stateMachine.nodes.find(n => n.id === nodeId)
    if (node) {
      setEditingNode(node)
      setNodeEditorOpen(true)
    }
    setSelectedNodeId(nodeId)
  }, [stateMachine])

  // Handle add node
  const handleAddNode = useCallback((type: CanvasNode['type'], x: number, y: number) => {
    const newNode: CanvasNode & { id: string; type: string; config?: Record<string, unknown>; description?: string } = {
      id: `node-${Date.now()}`,
      name: type.charAt(0).toUpperCase() + type.slice(1),
      type,
      x,
      y,
      width: 220,
      height: 80,
      config: {},
      description: ''
    }
    
    setStateMachine(prev => {
      if (!prev) return null
      return {
        ...prev,
        nodes: [...(prev.nodes || []), newNode]
      }
    })
    
    setCanvasNodes(prev => [...prev, {
      id: newNode.id,
      type,
      name: newNode.name,
      description: newNode.description,
      x,
      y,
      width: 220,
      height: 80
    }])
    
    setCanvasEdges(prev => {
      const startNode = (prev.map(e => e.sourceId) as string[]).find(s => 
        stateMachine?.nodes?.find(n => n.type === 'start' && n.id === s)
      )
      
      if (type === 'start' || !startNode) return prev
      return [...prev, {
        id: `edge-${Date.now()}`,
        sourceId: startNode,
        targetId: newNode.id,
        trigger: ''
      }]
    })
  }, [stateMachine])

  // Handle add edge
  const handleAddEdge = useCallback((from: string, to: string) => {
    setCanvasEdges(prev => [...prev, {
      id: `edge-${Date.now()}`,
      sourceId: from,
      targetId: to,
      trigger: ''
    }])
  }, [])

  // Handle delete node
  const handleDeleteNode = useCallback((nodeId: string) => {
    setStateMachine(prev => {
      if (!prev) return null
      return {
        ...prev,
        nodes: prev.nodes.filter(n => n.id !== nodeId),
        transitions: prev.transitions.filter(t => t.source_node !== nodeId && t.target_node !== nodeId)
      }
    })
    
    setCanvasNodes(prev => prev.filter(n => n.id !== nodeId))
    setCanvasEdges(prev => prev.filter(e => e.sourceId !== nodeId && e.targetId !== nodeId))
    
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(null)
      setEditingNode(null)
    }
  }, [selectedNodeId])

  // Handle delete edge
  const handleDeleteEdge = useCallback((edgeId: string) => {
    setCanvasEdges(prev => prev.filter(e => e.id !== edgeId))
    
    setStateMachine(prev => {
      if (!prev) return null
      return {
        ...prev,
        transitions: prev.transitions.filter(t => t.id !== edgeId)
      }
    })
  }, [])

  // Handle move node
  const handleMoveNode = useCallback((nodeId: string, x: number, y: number) => {
    setStateMachine(prev => {
      if (!prev) return null
      return {
        ...prev,
        nodes: prev.nodes.map(n => 
          n.id === nodeId ? { ...n, x, y } : n
        )
      }
    })
    
    setCanvasNodes(prev => prev.map(n => 
      n.id === nodeId ? { ...n, x, y } : n
    ))
  }, [])

  // Save state machine
  const handleSave = useCallback(async () => {
    if (!selectedCampaignId || !stateMachine) return
    
    try {
      setLoading(true)
      const graphData = {
        nodes: stateMachine.nodes,
        transitions: stateMachine.transitions
      }
      
      const response = await updateStateMachine(selectedCampaignId, {
        name: stateMachine.name,
        description: stateMachine.description,
        graph_data: graphData
      })
      
      if (response.data) {
        // Map to canvas format first
        const nodes: CanvasNode[] = (response.data.nodes || []).map(n => ({
          id: n.id,
          type: n.type as CanvasNode['type'] || 'state',
          name: n.name,
          description: n.description,
          x: n.x || 100,
          y: n.y || 100,
          width: 220,
          height: 80
        }))
        
        setCanvasNodes(nodes)
        setCanvasEdges((response.data.transitions || []).map(t => ({
          id: t.id,
          sourceId: t.source_node,
          targetId: t.target_node,
          trigger: t.label || ''
        })))
        
        // Create StateMachineData from response
        const stateMachineData: StateMachineData = {
          id: response.data.id,
          campaign_id: response.data.campaign_id,
          name: response.data.name,
          description: response.data.description,
          is_active: response.data.is_active,
          is_valid: response.data.is_valid,
          validation_errors: response.data.validation_errors,
          nodes: nodes.map(n => ({
            id: n.id,
            type: n.type,
            name: n.name,
            description: n.description,
            x: n.x,
            y: n.y,
            config: {},
            width: n.width,
            height: n.height
          })),
          transitions: (response.data.transitions || []).map(t => ({
            id: t.id,
            source_node: t.source_node,
            target_node: t.target_node,
            label: t.label,
            condition_type: t.condition_type
          }))
        }
        
        setStateMachine(stateMachineData)
        setError(null)
      } else {
        setError(response.error || 'Failed to save')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setLoading(false)
    }
  }, [selectedCampaignId, stateMachine])

  // Validate state machine
  const handleValidate = useCallback(async () => {
    if (!selectedCampaignId || !stateMachine || !stateMachine.id) return
    
    try {
      setValidating(true)
      const response = await validateStateMachine(selectedCampaignId, {
        id: stateMachine.id,
        campaign_id: selectedCampaignId,
        name: stateMachine.name,
        description: stateMachine.description,
        is_active: stateMachine.is_active ?? false,
        is_valid: stateMachine.is_valid ?? false,
        validation_errors: stateMachine.validation_errors || [],
        nodes: stateMachine.nodes,
        transitions: stateMachine.transitions
      })
      
      if (response.data) {
        setValidationResult({
          is_valid: response.data.is_valid,
          errors: response.data.errors || [],
          warnings: response.data.warnings?.map((w: { message: string }) => w.message) || []
        })
        
        if (response.data.is_valid) {
          // Auto-save if valid
          await handleSave()
        }
      } else {
        setError(response.error || 'Validation failed')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Validation failed')
    } finally {
      setValidating(false)
    }
  }, [selectedCampaignId, stateMachine, handleSave])

  // Simulate state machine
  const handleSimulate = useCallback(async () => {
    if (!selectedCampaignId || !selectedSimulationDeal) return
    
    try {
      setSimulating(true)
      const response = await simulateStateMachine(selectedCampaignId, selectedSimulationDeal)
      
      if (response.data) {
        setSimulationResult(response.data)
      } else {
        setError(response.error || 'Simulation failed')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed')
    } finally {
      setSimulating(false)
    }
  }, [selectedCampaignId, selectedSimulationDeal])

  // Sync canvas nodes and edges with stateMachine when it changes
  // This helps keep the visual editor in sync with the state machine data
  // Using useRef to track previous values to avoid unnecessary updates
  const previousStateMachineRef = useRef<StateMachineData | null>(null)
  
  useEffect(() => {
    if (!stateMachine) return
    
    // Check if nodes or transitions have actually changed to avoid unnecessary updates
    const nodesChanged = !previousStateMachineRef.current || 
      JSON.stringify(stateMachine.nodes) !== JSON.stringify(previousStateMachineRef.current.nodes)
    const edgesChanged = !previousStateMachineRef.current || 
      JSON.stringify(stateMachine.transitions) !== JSON.stringify(previousStateMachineRef.current.transitions)
    
    if (nodesChanged) {
      setCanvasNodes(stateMachine.nodes.map(n => ({
        id: n.id,
        type: n.type as CanvasNode['type'],
        name: n.name,
        description: n.description,
        x: n.x || 100,
        y: n.y || 100,
        width: 220,
        height: 80
      })))
    }
    
    if (edgesChanged) {
      setCanvasEdges(stateMachine.transitions.map(t => ({
        id: t.id,
        sourceId: t.source_node,
        targetId: t.target_node,
        trigger: t.label || ''
      })))
    }
    
    previousStateMachineRef.current = stateMachine
  }, [stateMachine])

  // Load initial campaigns on mount
  useEffect(() => {
    void (async () => {
      if (campaignId) {
        setSelectedCampaignId(campaignId)
      }
      await fetchCampaigns()
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId])

  // Fetch state machine when campaign changes
  useEffect(() => {
    if (selectedCampaignId) {
      void (async () => {
        await fetchStateMachine(selectedCampaignId)
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCampaignId])

  // Get node type color
  const getNodeColor = (type: string) => {
    switch (type) {
      case 'start': return 'border-emerald-500 bg-emerald-500/10'
      case 'end': return 'border-red-500 bg-red-500/10'
      case 'wait': return 'border-yellow-500 bg-yellow-500/10'
      default: return 'border-blue-500 bg-blue-500/10'
    }
  }

  if (loading && campaignsLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map(i => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16 mb-2" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">State Machine</h1>
          <p className="text-muted-foreground mt-1">
            Visual editor for campaign workflows
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleValidate} disabled={validating || !stateMachine}>
            {validating ? (
              <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Icons.CheckCircle className="mr-2 h-4 w-4" />
            )}
            Validate
          </Button>
          <Button onClick={handleSave} disabled={loading || !stateMachine}>
            <Icons.Save className="mr-2 h-4 w-4" />
            Save
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Campaign Select & Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Campaign</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={selectedCampaignId} onValueChange={handleCampaignChange}>
              <SelectTrigger>
                <SelectValue placeholder="Select Campaign" />
              </SelectTrigger>
              <SelectContent>
                {campaignsLoading ? (
                  <SelectItem value="loading" disabled>Loading...</SelectItem>
                ) : campaigns.length === 0 ? (
                  <SelectItem value="no-campaigns" disabled>No campaigns available</SelectItem>
                ) : (
                  campaigns.map(campaign => (
                    <SelectItem key={campaign.id} value={campaign.id}>
                      {campaign.name}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Nodes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stateMachine?.nodes?.length || 0}</div>
            <div className="text-xs text-muted-foreground">Total nodes in graph</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Transitions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stateMachine?.transitions?.length || 0}</div>
            <div className="text-xs text-muted-foreground">Total connections</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Status</CardTitle>
          </CardHeader>
          <CardContent>
            {stateMachine?.is_valid ? (
              <Badge className="bg-emerald-500 text-white hover:bg-emerald-600">
                Valid
              </Badge>
            ) : (
              <Badge variant="outline" className="border-yellow-500 text-yellow-600 dark:text-yellow-400">
                Needs Validation
              </Badge>
            )}
            <div className="text-xs text-muted-foreground mt-1">
              {stateMachine?.is_active ? 'Active' : 'Inactive'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="editor">
        <TabsList className="grid grid-cols-3 w-full md:w-auto">
          <TabsTrigger value="editor">Visual Editor</TabsTrigger>
          <TabsTrigger value="validation">Validation</TabsTrigger>
          <TabsTrigger value="simulation">Simulation</TabsTrigger>
        </TabsList>

        {/* Editor Tab */}
        <TabsContent value="editor" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Visual Workflow Editor</CardTitle>
              <CardDescription>
                Drag nodes, connect workflows, and configure conditions
              </CardDescription>
            </CardHeader>
            <CardContent className="h-[600px]">
              {campaigns.length === 0 ? (
                <div className="text-center py-12">
                  <Icons.Workflow className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No Campaigns Available</h3>
                  <p className="text-sm text-muted-foreground">
                    Create a campaign first to set up a state machine
                  </p>
                </div>
              ) : (
                <Canvas
                  nodes={canvasNodes}
                  edges={canvasEdges}
                  selectedNodeId={selectedNodeId || undefined}
                  onNodeClick={handleNodeClick}
                  onAddNode={handleAddNode}
                  onAddEdge={handleAddEdge}
                  onDeleteNode={handleDeleteNode}
                  onDeleteEdge={handleDeleteEdge}
                  onMoveNode={handleMoveNode}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Validation Tab */}
        <TabsContent value="validation" className="space-y-6">
          {validationResult ? (
            <Card>
              <CardHeader>
                <CardTitle>Validation Results</CardTitle>
                <CardDescription>
                  {validationResult.is_valid ? (
                    <Badge variant="default" className="bg-emerald-500">Validation Passed</Badge>
                  ) : (
                    <Badge variant="destructive">Validation Failed</Badge>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {validationResult.is_valid ? (
                  <div className="text-center py-8">
                    <Icons.CheckCircle className="h-16 w-16 mx-auto text-emerald-500 mb-4" />
                    <h3 className="text-xl font-semibold mb-2">State Machine is Valid</h3>
                    <p className="text-muted-foreground">
                      Your workflow is ready to use
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {validationResult.errors.map((error, i) => (
                      <Alert key={i} variant="destructive">
                        <Icons.AlertCircle className="h-4 w-4" />
                        <AlertDescription>{error}</AlertDescription>
                      </Alert>
                    ))}
                    {validationResult.warnings.map((warning, i) => (
                      <Alert key={i} variant="default">
                        <Icons.AlertTriangle className="h-4 w-4" />
                        <AlertDescription>{warning}</AlertDescription>
                      </Alert>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>No Validation Results</CardTitle>
                <CardDescription>
                  Click "Validate" to check your state machine
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </TabsContent>

        {/* Simulation Tab */}
        <TabsContent value="simulation" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Simulation</CardTitle>
              <CardDescription>
                Test your workflow with different leads
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="simulation-deal">Select Lead</Label>
                <Select 
                  value={selectedSimulationDeal} 
                  onValueChange={setSelectedSimulationDeal}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a lead to simulate" />
                  </SelectTrigger>
                  <SelectContent>
                    {simulationDeals.length === 0 ? (
                      <SelectItem value="no-deals" disabled>No simulation data available</SelectItem>
                    ) : (
                      simulationDeals.map(deal => (
                        <SelectItem key={deal} value={deal}>
                          {deal}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <Button 
                onClick={handleSimulate} 
                disabled={simulating || !selectedSimulationDeal}
                className="w-full"
              >
                {simulating ? (
                  <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Icons.Play className="mr-2 h-4 w-4" />
                )}
                Simulate
              </Button>

              {simulationResult && (
                <div className="space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle>Simulation Result</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Status:</span>
                        <Badge variant={simulationResult.simulation.completed ? 'default' : 'outline'}>
                          {simulationResult.simulation.completed ? 'Completed' : 'Incomplete'}
                        </Badge>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Steps:</span>
                        <span className="font-medium">{simulationResult.simulation.steps}</span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Nodes Visited:</span>
                        <span className="font-medium">{simulationResult.simulation.nodes_visited}</span>
                      </div>

                      <div className="space-y-2">
                        <h4 className="font-medium">Simulation Path</h4>
                        <div className="space-y-2">
                          {simulationResult.simulation.path.map((step, i) => (
                            <div key={i} className="flex items-center gap-2 text-sm">
                              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-medium">
                                {i + 1}
                              </span>
                              <span className="flex-1 truncate">{step.name} ({step.type})</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {simulationResult.simulation.messages_sent.length > 0 && (
                        <div className="space-y-2">
                          <h4 className="font-medium">Messages Sent</h4>
                          <ul className="list-disc list-inside space-y-1 text-sm">
                            {simulationResult.simulation.messages_sent.map((msg, i) => (
                              <li key={i} className="text-muted-foreground">{msg}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {simulationResult.simulation.error && (
                        <Alert variant="destructive">
                          <Icons.AlertCircle className="h-4 w-4" />
                          <AlertDescription>{simulationResult.simulation.error}</AlertDescription>
                        </Alert>
                      )}
                    </CardContent>
                  </Card>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Node Editor Dialog */}
      {editingNode && (
        <Dialog open={nodeEditorOpen} onOpenChange={setNodeEditorOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Node: {editingNode.name}</DialogTitle>
              <DialogDescription>
                Configure node properties
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="node-name">Name</Label>
                <Input
                  id="node-name"
                  value={editingNode.name}
                  onChange={(e) => setEditingNode(prev => prev ? { ...prev, name: e.target.value } : null)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="node-type">Type</Label>
                <Select 
                  value={editingNode.type} 
                  onValueChange={(type) => setEditingNode(prev => prev ? { ...prev, type: type as CanvasNode['type'] } : null)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="start">Start</SelectItem>
                    <SelectItem value="state">State</SelectItem>
                    <SelectItem value="wait">Wait</SelectItem>
                    <SelectItem value="message">Message</SelectItem>
                    <SelectItem value="gate">Gate</SelectItem>
                    <SelectItem value="decision">Decision</SelectItem>
                    <SelectItem value="branch">Branch</SelectItem>
                    <SelectItem value="end">End</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="node-desc">Description</Label>
                <textarea
                  id="node-desc"
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={editingNode.description}
                  onChange={(e) => setEditingNode(prev => prev ? { ...prev, description: e.target.value } : null)}
                  placeholder="Node description..."
                />
              </div>
            </div>

            <Button 
              variant="outline" 
              className="w-full"
              onClick={() => {
                if (!stateMachine) return
                const updatedNodes = stateMachine.nodes.map(n => 
                  n.id === editingNode.id ? { ...n, ...editingNode } : n
                )
                setStateMachine({ ...stateMachine, nodes: updatedNodes })
                setNodeEditorOpen(false)
              }}
            >
              Save Changes
            </Button>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

export default StateMachinePage