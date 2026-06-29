'use client'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/lib/types/components'
import { CampaignTemplate } from '@/lib/types/components'

import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'

interface TemplateCardProps {
  template: CampaignTemplate
  onClick?: () => void
  onEdit?: (template: CampaignTemplate) => void
  onDelete?: (template: CampaignTemplate) => void
  onClone?: (template: CampaignTemplate) => void
  onCreateCampaign?: (template: CampaignTemplate) => void
  className?: string
}

const statusColors = {
  public: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
  private: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20',
}

const TemplateCard = ({
  template,
  onClick,
  onEdit,
  onDelete,
  onClone,
  onCreateCampaign,
  className,
}: TemplateCardProps) => {
  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    onEdit?.(template)
  }

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    onDelete?.(template)
  }

  const handleClone = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClone?.(template)
  }

  const handleCreateCampaign = (e: React.MouseEvent) => {
    e.stopPropagation()
    onCreateCampaign?.(template)
  }

  const isPublic = template.is_public

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all hover:shadow-md',
        className,
      )}
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="text-base">{template.name}</CardTitle>
            <CardDescription className="line-clamp-2">
              {template.description || 'No description'}
            </CardDescription>
          </div>
          <Badge variant="outline" className={cn('text-xs', statusColors[isPublic ? 'public' : 'private'])}>
            {isPublic ? 'Public' : 'Private'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="text-center">
            <div className="text-lg font-bold">{template.velocity || 20}</div>
            <div className="text-xs text-muted-foreground">Daily Velocity</div>
          </div>
          <div className="text-center border-l">
            <div className="text-lg font-bold">
              {template.cooldown_minutes ? `${template.cooldown_minutes} min` : 'No cooldown'}
            </div>
            <div className="text-xs text-muted-foreground">Cooldown</div>
          </div>
        </div>

        <div className="space-y-2">
          {template.campaign_objective && (
            <div className="flex items-center gap-2 text-sm">
              <Icons.Briefcase className="h-3 w-3 text-muted-foreground" />
              <span className="text-muted-foreground">Objective:</span>
              <span className="font-medium truncate">{template.campaign_objective}</span>
            </div>
          )}

          <div className="flex items-center gap-2 text-sm">
            <Icons.Shield className="h-3 w-3 text-muted-foreground" />
            <span className="text-muted-foreground">Ghost mode:</span>
            <span className={cn('font-medium', template.ghost_mode_enabled ? 'text-emerald-600' : 'text-muted-foreground')}>
              {template.ghost_mode_enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Icons.Clock className="h-3 w-3" />
            Created {formatDistanceToNow(new Date(template.created_at), { addSuffix: true })}
          </div>

          <div className="flex gap-2">
            <Button size="sm" variant="default" onClick={handleCreateCampaign}>
              <Icons.Play className="h-4 w-4" />
              Campaign
            </Button>
            <Button size="sm" variant="ghost" onClick={handleClone}>
              <Icons.Clipboard className="h-4 w-4" />
            </Button>
            <Button size="sm" variant="ghost" onClick={handleEdit}>
              <Icons.Edit className="h-4 w-4" />
            </Button>
            <Button size="sm" variant="ghost" onClick={handleDelete}>
              <Icons.Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export { TemplateCard, statusColors }