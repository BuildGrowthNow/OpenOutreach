'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Icons } from '@/lib/types/components'

interface LeadNotesProps {
  notes?: string
  onSave?: (content: string) => Promise<void>
  isSaving?: boolean
  leadName?: string
}

export function LeadNotes({
  notes = '',
  onSave,
  isSaving = false,
  leadName = 'Lead'
}: LeadNotesProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(notes)

  const handleSave = async () => {
    if (!onSave) return
    await onSave(draft)
    setEditing(false)
  }

  const handleCancel = () => {
    setDraft(notes)
    setEditing(false)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Notes</CardTitle>
          {!editing && onSave && (
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
              <Icons.Edit className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {editing ? (
          <>
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={`Add notes about ${leadName}...`}
              className="min-h-[120px] resize-none"
              disabled={isSaving}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="outline" onClick={handleCancel} disabled={isSaving}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave} disabled={isSaving}>
                {isSaving ? <Icons.RefreshCw className="h-4 w-4 animate-spin" /> : 'Save'}
              </Button>
            </div>
          </>
        ) : (
          <div
            className="min-h-[60px] text-sm whitespace-pre-wrap cursor-pointer rounded-md p-2 hover:bg-muted/50 transition-colors"
            onClick={() => onSave && setEditing(true)}
          >
            {notes ? (
              notes
            ) : (
              <span className="text-muted-foreground italic">
                No notes yet. Click to add notes about {leadName}.
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
