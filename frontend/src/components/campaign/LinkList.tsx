'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Icons } from '@/lib/types/components'
import { TrackedLink } from '@/lib/api/dashboard'
import { cn } from '@/lib/utils'

interface LinkListProps {
  links: TrackedLink[]
  onEdit: (link: TrackedLink) => void
  onDelete: (link: TrackedLink) => void
  onViewStats: (link: TrackedLink) => void
}

export function LinkList({ links, onEdit, onDelete, onViewStats }: LinkListProps) {
  const router = useRouter()
  const [sortConfig, setSortConfig] = useState<{ key: keyof TrackedLink; direction: 'asc' | 'desc' } | null>(null)

  const sortedLinks = [...links].sort((a, b) => {
    if (!sortConfig) return 0
    const aValue = a[sortConfig.key]
    const bValue = b[sortConfig.key]
    
    if (aValue === bValue) return 0
    if (aValue === undefined) return sortConfig.direction === 'asc' ? -1 : 1
    if (bValue === undefined) return sortConfig.direction === 'asc' ? 1 : -1
    
    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortConfig.direction === 'asc' 
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue)
    }
    
    const numA = typeof aValue === 'number' ? aValue : 0
    const numB = typeof bValue === 'number' ? bValue : 0
    return sortConfig.direction === 'asc' ? numA - numB : numB - numA
  })

  const handleSort = (key: keyof TrackedLink) => {
    let direction: 'asc' | 'desc' = 'asc'
    if (sortConfig && sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc'
    }
    setSortConfig({ key, direction })
  }

  const getStatusColor = (status: boolean) => {
    return status 
      ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
      : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
  }

  const formatClicks = (count: number) => {
    if (count >= 1000000) {
      return `${(count / 1000000).toFixed(1)}M`
    }
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}K`
    }
    return count.toString()
  }

  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead 
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => handleSort('original_url')}
            >
              URL
              {sortConfig?.key === 'original_url' && (
                <Icons.ChevronDown className="ml-1 h-4 w-4 inline" />
              )}
            </TableHead>
            <TableHead>Short Code</TableHead>
            <TableHead 
              className="cursor-pointer hover:bg-muted/50 text-right"
              onClick={() => handleSort('total_clicks')}
            >
              Total Clicks
              {sortConfig?.key === 'total_clicks' && (
                <Icons.ChevronDown className="ml-1 h-4 w-4 inline" />
              )}
            </TableHead>
            <TableHead 
              className="cursor-pointer hover:bg-muted/50 text-right"
              onClick={() => handleSort('is_active')}
            >
              Status
              {sortConfig?.key === 'is_active' && (
                <Icons.ChevronDown className="ml-1 h-4 w-4 inline" />
              )}
            </TableHead>
            <TableHead>Last Clicked</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedLinks.length > 0 ? (
            sortedLinks.map((link) => (
              <TableRow key={link.id}>
                <TableCell className="max-w-[250px] truncate font-medium">
                  <a 
                    href={link.original_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline hover:text-blue-700"
                  >
                    {link.original_url}
                  </a>
                </TableCell>
                <TableCell>
                  <code className="bg-muted px-2 py-1 rounded text-sm">
                    {link.short_code}
                  </code>
                </TableCell>
                <TableCell className="text-right font-bold text-emerald-600 dark:text-emerald-400">
                  {formatClicks(link.total_clicks || 0)}
                </TableCell>
                <TableCell className="text-right">
                  <Badge variant="outline" className={cn('text-xs', getStatusColor(link.is_active ?? true))}>
                    {link.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </TableCell>
                <TableCell>
                  {link.last_clicked_at ? (
                    <span className="text-sm text-muted-foreground">
                      {new Date(link.last_clicked_at).toLocaleDateString()}
                    </span>
                  ) : (
                    <span className="text-sm text-muted-foreground italic">Never</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onViewStats(link)}
                      title="View Analytics"
                    >
                      <Icons.BarChart3 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(link)}
                      title="Edit Link"
                    >
                      <Icons.Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onDelete(link)}
                      title="Delete Link"
                      className="text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-900/20"
                    >
                      <Icons.Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                <div className="flex flex-col items-center gap-2">
                  <Icons.Link className="h-8 w-8 opacity-50" />
                  <p>No tracked links found</p>
                </div>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}