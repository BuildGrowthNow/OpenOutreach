'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'

interface Node {
  id: string
  type: 'state' | 'start' | 'end'
  name: string
  description?: string
  x: number
  y: number
  width: number
  height: number
}

interface Edge {
  id: string
  sourceId: string
  targetId: string
  trigger: string
  description?: string
}

interface CanvasProps {
  nodes: Node[]
  edges: Edge[]
  selectedNodeId?: string
  onNodeClick?: (nodeId: string) => void
  onAddNode?: (type: Node['type'], x: number, y: number) => void
  onAddEdge?: (from: string, to: string) => void
  onDeleteNode?: (nodeId: string) => void
  onDeleteEdge?: (edgeId: string) => void
  onMoveNode?: (nodeId: string, x: number, y: number) => void
  readOnly?: boolean
}

export function Canvas({
  nodes,
  edges,
  selectedNodeId,
  onNodeClick,
  onAddNode,
  onAddEdge,
  onDeleteNode,
  onDeleteEdge,
  onMoveNode,
  readOnly = false
}: CanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId?: string; edgeId?: string } | null>(null)

  const getNodeColor = (type: Node['type']) => {
    switch (type) {
      case 'start':
        return 'border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
      case 'end':
        return 'border-red-500 bg-red-500/10 text-red-600 dark:text-red-400'
      default:
        return 'border-blue-500 bg-blue-500/10 text-blue-600 dark:text-blue-400'
    }
  }

  const getEdgeColor = () => {
    return 'stroke-blue-400'
  }

  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const x = (e.clientX - rect.left - offset.x) / scale
    const y = (e.clientY - rect.top - offset.y) / scale

    // Check if clicking on a node
    for (const node of nodes) {
      if (
        x >= node.x && x <= node.x + node.width &&
        y >= node.y && y <= node.y + node.height
      ) {
        if (onNodeClick) {
          onNodeClick(node.id)
        }
        return
      }
    }

    // Clear selection if clicking empty space
    if (onNodeClick && selectedNodeId) {
      onNodeClick('')
    }
  }, [nodes, offset, scale, selectedNodeId, onNodeClick])

  const handleMouseDown = useCallback((e: React.MouseEvent, nodeId: string) => {
    if (readOnly) return
    setIsDragging(true)
    setDragStart({ x: e.clientX, y: e.clientY })
    setDraggedNodeId(nodeId)
  }, [readOnly])

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging || !draggedNodeId || !onMoveNode) return

    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const deltaX = (e.clientX - dragStart.x) / scale
    const deltaY = (e.clientY - dragStart.y) / scale

    const node = nodes.find(n => n.id === draggedNodeId)
    if (node) {
      const newX = Math.max(0, node.x + deltaX)
      const newY = Math.max(0, node.y + deltaY)
      onMoveNode(draggedNodeId, newX, newY)
    }

    setDragStart({ x: e.clientX, y: e.clientY })
  }, [isDragging, draggedNodeId, dragStart, scale, nodes, onMoveNode])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
    setDraggedNodeId(null)
  }, [])

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  const handleContextMenu = useCallback((e: React.MouseEvent, nodeId?: string, edgeId?: string) => {
    e.preventDefault()
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      nodeId,
      edgeId
    })
  }, [])

  const handleZoomIn = () => {
    setScale(prev => Math.min(prev + 0.1, 2))
  }

  const handleZoomOut = () => {
    setScale(prev => Math.max(prev - 0.1, 0.5))
  }

  const handleResetView = () => {
    setScale(1)
    setOffset({ x: 0, y: 0 })
  }

  const handleAddStartNode = () => {
    if (!onAddNode) return
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const x = Math.random() * rect.width * 0.7
    const y = Math.random() * rect.height * 0.7
    onAddNode('start', x, y)
  }

  const handleAddStateNode = () => {
    if (!onAddNode) return
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const x = Math.random() * rect.width * 0.7
    const y = Math.random() * rect.height * 0.7
    onAddNode('state', x, y)
  }

  const handleAddEndNode = () => {
    if (!onAddNode) return
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const x = Math.random() * rect.width * 0.7
    const y = Math.random() * rect.height * 0.7
    onAddNode('end', x, y)
  }

  return (
    <div className="relative w-full h-full">
      {/* Control Bar */}
      {!readOnly && (
        <div className="absolute top-4 left-4 z-10 flex gap-2 p-2 bg-white dark:bg-gray-800 rounded-lg shadow-lg border">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleZoomIn}
            title="Zoom In"
          >
            <Icons.ZoomIn className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleZoomOut}
            title="Zoom Out"
          >
            <Icons.ZoomOut className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleResetView}
            title="Reset View"
          >
            <Icons.Home className="h-4 w-4" />
          </Button>
          <div className="w-px bg-gray-200 dark:bg-gray-700 mx-2" />
          <Button
            variant="ghost"
            size="icon"
            onClick={handleAddStartNode}
            title="Add Start Node"
          >
            <Icons.Play className="h-4 w-4 text-emerald-500" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleAddStateNode}
            title="Add State Node"
          >
            <Icons.Circle className="h-4 w-4 text-blue-500" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleAddEndNode}
            title="Add End Node"
          >
            <Icons.StopCircle className="h-4 w-4 text-red-500" />
          </Button>
        </div>
      )}

      {/* Canvas */}
      <div
        ref={canvasRef}
        className="w-full h-full min-h-[500px] bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-950 border rounded-lg relative overflow-hidden"
        onClick={handleCanvasClick}
        onContextMenu={(e) => handleContextMenu(e)}
      >
        {/* Grid Pattern */}
        <div className="absolute inset-0 opacity-20">
          <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
                <path d="M 50 0 L 0 0 0 50" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.3" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>
        </div>

        {/* Container for scaled content */}
        <div
          className="absolute"
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
            transformOrigin: '0 0',
            width: '100%',
            height: '100%'
          }}
        >
          {/* Edges */}
          <svg className="absolute inset-0 pointer-events-none">
            {edges.map(edge => {
              const sourceNode = nodes.find(n => n.id === edge.sourceId)
              const targetNode = nodes.find(n => n.id === edge.targetId)
              
              if (!sourceNode || !targetNode) return null

              const startX = sourceNode.x + sourceNode.width / 2
              const startY = sourceNode.y + sourceNode.height / 2
              const endX = targetNode.x + targetNode.width / 2
              const endY = targetNode.y + targetNode.height / 2

              return (
                <g key={edge.id}>
                  <line
                    x1={startX}
                    y1={startY}
                    x2={endX}
                    y2={endY}
                    className={getEdgeColor()}
                    strokeWidth="2"
                    markerEnd="url(#arrowhead)"
                  />
                  {/* Edge label */}
                  {edge.trigger && (
                    <g transform={`translate(${(startX + endX) / 2}, ${(startY + endY) / 2})`}>
                      <rect
                        x="-20"
                        y="-12"
                        width="40"
                        height="24"
                        className="fill-white dark:fill-gray-800 stroke-blue-400"
                        strokeWidth="1"
                        rx="4"
                      />
                      <text
                        textAnchor="middle"
                        className="text-xs fill-blue-600 dark:fill-blue-400 font-medium"
                      >
                        {edge.trigger}
                      </text>
                    </g>
                  )}
                </g>
              )
            })}
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon
                  points="0 0, 10 3.5, 0 7"
                  className="fill-blue-400"
                />
              </marker>
            </defs>
          </svg>

          {/* Nodes */}
          {nodes.map(node => (
            <div
              key={node.id}
              className={cn(
                'absolute border-2 rounded-lg p-3 shadow-lg cursor-move',
                getNodeColor(node.type),
                selectedNodeId === node.id && 'ring-2 ring-offset-2 ring-blue-500',
                node.type === 'start' && 'border-emerald-500',
                node.type === 'end' && 'border-red-500'
              )}
              style={{
                left: `${node.x}px`,
                top: `${node.y}px`,
                width: `${node.width}px`,
                height: `${node.height}px`,
              }}
              onClick={(e) => {
                e.stopPropagation()
                if (onNodeClick) {
                  onNodeClick(node.id)
                }
              }}
              onMouseDown={(e) => handleMouseDown(e, node.id)}
              onContextMenu={(e) => handleContextMenu(e, node.id)}
            >
              <div className="flex flex-col items-center justify-center h-full">
                <div className="flex items-center gap-2 mb-2">
                  {node.type === 'start' && (
                    <Icons.Play className="h-4 w-4 text-emerald-500" />
                  )}
                  {node.type === 'end' && (
                    <Icons.StopCircle className="h-4 w-4 text-red-500" />
                  )}
                  {node.type === 'state' && (
                    <Icons.Circle className="h-4 w-4 text-blue-500" />
                  )}
                  <span className="font-semibold truncate">{node.name}</span>
                </div>
                {node.description && (
                  <p className="text-xs text-muted-foreground text-center line-clamp-2">
                    {node.description}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Empty state */}
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <Icons.Workflow className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">Empty Canvas</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Start building your workflow by adding states and transitions
              </p>
              {!readOnly && (
                <div className="flex gap-2 justify-center">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleAddStartNode}
                  >
                    <Icons.Play className="mr-2 h-4 w-4" />
                    Add Start
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleAddStateNode}
                  >
                    <Icons.Circle className="mr-2 h-4 w-4" />
                    Add State
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div
          className="fixed z-50 w-48 bg-white dark:bg-gray-800 border rounded-lg shadow-lg"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {contextMenu.nodeId && (
            <>
              <div className="p-2 border-b">
                <span className="text-sm font-medium">Node Actions</span>
              </div>
              {!readOnly && (
                <>
                  <button
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                    onClick={() => {
                      if (onDeleteNode && contextMenu.nodeId) {
                        onDeleteNode(contextMenu.nodeId)
                      }
                      setContextMenu(null)
                    }}
                  >
                    <Icons.Trash2 className="h-4 w-4" />
                    Delete Node
                  </button>
                  <button
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                    onClick={() => setContextMenu(null)}
                  >
                    <Icons.Edit className="h-4 w-4" />
                    Edit Node
                  </button>
                </>
              )}
            </>
          )}
          {contextMenu.edgeId && !readOnly && (
            <>
              <div className="p-2 border-b">
                <span className="text-sm font-medium">Edge Actions</span>
              </div>
              <button
                className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                onClick={() => {
                  if (onDeleteEdge && contextMenu.edgeId) {
                    onDeleteEdge(contextMenu.edgeId)
                  }
                  setContextMenu(null)
                }}
              >
                <Icons.Trash2 className="h-4 w-4" />
                Delete Edge
              </button>
            </>
          )}
          <div className="p-2 border-t">
            <button
              className="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700"
              onClick={() => setContextMenu(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}