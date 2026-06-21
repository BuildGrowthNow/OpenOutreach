'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'

interface EdgeProps {
  id: string
  sourceId: string
  targetId: string
  trigger: string
  description?: string
  conditions?: Record<string, unknown>[]
  actions?: Record<string, unknown>[]
  sourceName?: string
  targetName?: string
  onUpdate?: (id: string, data: { trigger: string; description?: string }) => void
  onDelete?: (id: string) => void
  readOnly?: boolean
}

export function Edge({
  id,
  sourceId,
  targetId,
  trigger,
  description,
  conditions = [],
  actions = [],
  sourceName = sourceId,
  targetName = targetId,
  onUpdate,
  onDelete,
  readOnly = false
}: EdgeProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editTrigger, setEditTrigger] = useState(trigger)
  const [editDescription, setEditDescription] = useState(description || '')
  const [isHovered, setIsHovered] = useState(false)

  const handleSave = () => {
    if (onUpdate) {
      onUpdate(id, {
        trigger: editTrigger.trim(),
        description: editDescription.trim() || undefined
      })
    }
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditTrigger(trigger)
    setEditDescription(description || '')
    setIsEditing(false)
  }

  const handleDelete = () => {
    if (onDelete) {
      onDelete(id)
    }
  }

  if (isEditing) {
    return (
      <Card className="border-2 border-blue-500/20">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Edit Transition</CardTitle>
          <CardDescription>
            From {sourceName} to {targetName}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Trigger Event</label>
            <Input
              value={editTrigger}
              onChange={(e) => setEditTrigger(e.target.value)}
              placeholder="e.g., RESPONSE_RECEIVED"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Description</label>
            <Textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="Optional description of what triggers this transition"
              rows={2}
            />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleSave}>
              Save
            </Button>
            <Button size="sm" variant="outline" onClick={handleCancel}>
              Cancel
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div
      className="relative"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Card className={cn(
        'border-2 border-blue-500/20 bg-blue-500/5 transition-all duration-200',
        isHovered && 'scale-105'
      )}>
        {isHovered && !readOnly && (
          <div className="absolute -top-2 -right-2 z-10 flex gap-1">
            <Button
              size="icon"
              variant="secondary"
              className="h-6 w-6"
              onClick={() => setIsEditing(true)}
              title="Edit transition"
            >
              <Icons.Edit className="h-3 w-3" />
            </Button>
            <Button
              size="icon"
              variant="destructive"
              className="h-6 w-6"
              onClick={handleDelete}
              title="Delete transition"
            >
              <Icons.Trash2 className="h-3 w-3" />
            </Button>
          </div>
        )}

        <CardContent className="pt-6">
          <div className="space-y-4">
            {/* Header with arrow visualization */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="px-3 py-1 rounded bg-blue-500/10 border border-blue-500/20">
                  <span className="text-sm font-medium">{sourceName}</span>
                </div>
                <div className="flex flex-col items-center">
                  <Icons.ArrowRight className="h-4 w-4" />
                  <Badge variant="outline" className="text-xs">
                    {trigger}
                  </Badge>
                </div>
                <div className="px-3 py-1 rounded bg-blue-500/10 border border-blue-500/20">
                  <span className="text-sm font-medium">{targetName}</span>
                </div>
              </div>
            </div>

            {/* Description */}
            {description && (
              <p className="text-sm text-muted-foreground">
                {description}
              </p>
            )}

            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="space-y-1">
                <div className="flex items-center gap-1">
                  <Icons.Filter className="h-3 w-3" />
                  <span className="font-medium">Conditions</span>
                </div>
                {conditions.length > 0 ? (
                  <div className="text-muted-foreground">
                    {conditions.length} condition{conditions.length !== 1 ? 's' : ''}
                  </div>
                ) : (
                  <div className="text-muted-foreground">No conditions</div>
                )}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-1">
                  <Icons.Zap className="h-3 w-3" />
                  <span className="font-medium">Actions</span>
                </div>
                {actions.length > 0 ? (
                  <div className="text-muted-foreground">
                    {actions.length} action{actions.length !== 1 ? 's' : ''}
                  </div>
                ) : (
                  <div className="text-muted-foreground">No actions</div>
                )}
              </div>
            </div>

            {/* ID */}
            <div className="text-xs text-muted-foreground flex items-center justify-center gap-1 mt-4">
              <Icons.Hash className="h-3 w-3" />
              <span>Transition ID: {id}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
