'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'

interface NodeProps {
  id: string
  type: 'state' | 'start' | 'end'
  name: string
  description?: string
  isSelected?: boolean
  isStartState?: boolean
  isEndState?: boolean
  onUpdate?: (id: string, data: { name: string; description?: string }) => void
  onDelete?: (id: string) => void
  onSetAsStart?: (id: string) => void
  onSetAsEnd?: (id: string) => void
  readOnly?: boolean
}

export function Node({
  id,
  type,
  name,
  description,
  isSelected = false,
  isStartState = false,
  isEndState = false,
  onUpdate,
  onDelete,
  onSetAsStart,
  onSetAsEnd,
  readOnly = false
}: NodeProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState(name)
  const [editDescription, setEditDescription] = useState(description || '')
  const [isHovered, setIsHovered] = useState(false)

  const getNodeColor = () => {
    switch (type) {
      case 'start':
        return 'border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
      case 'end':
        return 'border-red-500 bg-red-500/10 text-red-600 dark:text-red-400'
      default:
        return 'border-blue-500 bg-blue-500/10 text-blue-600 dark:text-blue-400'
    }
  }

  const getNodeIcon = () => {
    switch (type) {
      case 'start':
        return <Icons.Play className="h-4 w-4" />
      case 'end':
        return <Icons.StopCircle className="h-4 w-4" />
      default:
        return <Icons.Circle className="h-4 w-4" />
    }
  }

  const handleSave = () => {
    if (onUpdate) {
      onUpdate(id, {
        name: editName.trim(),
        description: editDescription.trim() || undefined
      })
    }
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditName(name)
    setEditDescription(description || '')
    setIsEditing(false)
  }

  const handleDelete = () => {
    if (onDelete) {
      onDelete(id)
    }
  }

  const handleSetAsStart = () => {
    if (onSetAsStart) {
      onSetAsStart(id)
    }
  }

  const handleSetAsEnd = () => {
    if (onSetAsEnd) {
      onSetAsEnd(id)
    }
  }

  if (isEditing) {
    return (
      <Card className={cn('border-2', getNodeColor())}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            {getNodeIcon()}
            <span>Edit Node</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Name</label>
            <Input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="Enter node name"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Description</label>
            <Textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="Optional description"
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
      className={cn(
        'relative transition-all duration-200',
        isSelected && 'scale-105'
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Card className={cn('border-2 relative', getNodeColor())}>
        {isHovered && !readOnly && (
          <div className="absolute -top-2 -right-2 z-10 flex gap-1">
            <Button
              size="icon"
              variant="secondary"
              className="h-6 w-6"
              onClick={() => setIsEditing(true)}
              title="Edit node"
            >
              <Icons.Edit className="h-3 w-3" />
            </Button>
            <Button
              size="icon"
              variant="destructive"
              className="h-6 w-6"
              onClick={handleDelete}
              title="Delete node"
            >
              <Icons.Trash2 className="h-3 w-3" />
            </Button>
          </div>
        )}

        <CardContent className="pt-6">
          <div className="flex flex-col items-center text-center">
            <div className="mb-3">
              <div className="flex items-center gap-2 justify-center">
                {getNodeIcon()}
                <h4 className="font-semibold truncate max-w-[150px]">{name}</h4>
                {isStartState && (
                  <Badge variant="outline" className="text-xs">
                    Start
                  </Badge>
                )}
                {isEndState && (
                  <Badge variant="outline" className="text-xs">
                    End
                  </Badge>
                )}
              </div>
              {description && (
                <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
                  {description}
                </p>
              )}
            </div>

            {/* Action buttons */}
            {!readOnly && (
              <div className="flex flex-wrap gap-2 mt-4">
                {type === 'state' && !isStartState && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-xs h-7"
                    onClick={handleSetAsStart}
                  >
                    <Icons.Play className="mr-1 h-3 w-3" />
                    Set Start
                  </Button>
                )}
                {type === 'state' && !isEndState && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-xs h-7"
                    onClick={handleSetAsEnd}
                  >
                    <Icons.StopCircle className="mr-1 h-3 w-3" />
                    Set End
                  </Button>
                )}
              </div>
            )}

            {/* Node metadata */}
            <div className="mt-4 text-xs text-muted-foreground">
              <div className="flex items-center justify-center gap-1">
                <Icons.Hash className="h-3 w-3" />
                <span>{id}</span>
              </div>
              <div className="flex items-center justify-center gap-1 mt-1">
                <Icons.Type className="h-3 w-3" />
                <span className="capitalize">{type}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}