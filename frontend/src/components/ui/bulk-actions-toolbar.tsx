'use client'

import { useMemo } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Icons } from '@/lib/types/components'
import { cn } from '@/lib/utils'

export interface BulkAction {
  id: string
  label: string
  icon?: React.ReactNode
  variant?: 'default' | 'destructive'
  onClick: (selectedIds: string[]) => void | Promise<void>
  disabled?: (selectedIds: string[]) => boolean
}

interface BulkActionsToolbarProps {
  selectedIds: Set<string>
  totalItems: number
  onSelectAll: (selected: boolean) => void
  onSelectNone: () => void
  actions: BulkAction[]
  isLoading?: boolean
  className?: string
}

export function BulkActionsToolbar({
  selectedIds,
  totalItems,
  onSelectAll,
  onSelectNone,
  actions,
  isLoading = false,
  className,
}: BulkActionsToolbarProps) {
  const selectedCount = selectedIds.size
  const allSelected = selectedCount === totalItems && totalItems > 0
  const someSelected = selectedCount > 0 && !allSelected

  const destructiveActions = useMemo(
    () => actions.filter((a) => a.variant === 'destructive'),
    [actions],
  )

  const normalActions = useMemo(
    () => actions.filter((a) => a.variant !== 'destructive'),
    [actions],
  )

  if (selectedCount === 0) {
    return null
  }

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-4 px-4 py-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg',
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <Checkbox
          checked={allSelected}
          ref={(el) => {
            if (el) {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              (el as any).indeterminate = someSelected
            }
          }}
          onCheckedChange={(checked) => {
            if (checked) {
              onSelectAll(true)
            } else {
              onSelectNone()
            }
          }}
          aria-label="Select all items"
        />
        <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
          {selectedCount} {selectedCount === 1 ? 'item' : 'items'} selected
        </span>
        {selectedCount < totalItems && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
            onClick={() => onSelectAll(true)}
          >
            Select all {totalItems}
          </Button>
        )}
      </div>

      <div className="flex items-center gap-2">
        {normalActions.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="sm"
                disabled={isLoading || selectedCount === 0}
              >
                <Icons.MoreHorizontal className="h-4 w-4 mr-2" />
                Actions
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {normalActions.map((action) => {
                const isDisabled = action.disabled ? action.disabled(Array.from(selectedIds)) : false
                return (
                  <DropdownMenuItem
                    key={action.id}
                    onClick={() => action.onClick(Array.from(selectedIds))}
                    disabled={isDisabled || isLoading}
                  >
                    {action.icon && <span className="mr-2">{action.icon}</span>}
                    {action.label}
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        {destructiveActions.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="sm"
                variant="destructive"
                disabled={isLoading || selectedCount === 0}
              >
                <Icons.Trash2 className="h-4 w-4 mr-2" />
                Danger
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {destructiveActions.map((action) => {
                const isDisabled = action.disabled ? action.disabled(Array.from(selectedIds)) : false
                return (
                  <DropdownMenuItem
                    key={action.id}
                    onClick={() => action.onClick(Array.from(selectedIds))}
                    disabled={isDisabled || isLoading}
                    className="text-red-600 dark:text-red-400 focus:text-red-600 dark:focus:text-red-400 focus:bg-red-50 dark:focus:bg-red-950/20"
                  >
                    {action.icon && <span className="mr-2">{action.icon}</span>}
                    {action.label}
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={onSelectNone}
          disabled={isLoading}
        >
          Clear
        </Button>
      </div>
    </div>
  )
}
