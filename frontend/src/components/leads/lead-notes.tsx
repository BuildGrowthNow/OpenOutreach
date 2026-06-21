'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Icons } from '@/lib/types/components'
import { formatDistanceToNow } from 'date-fns'

interface Note {
  id: string
  content: string
  createdBy: string
  createdAt: string
  updatedAt?: string
}

interface LeadNotesProps {
  notes?: Note[]
  onAddNote?: (content: string) => Promise<void>
  onEditNote?: (noteId: string, content: string) => Promise<void>
  onDeleteNote?: (noteId: string) => Promise<void>
  isLoading?: boolean
  isSaving?: boolean
  leadName?: string
}

export function LeadNotes({
  notes = [],
  onAddNote,
  onEditNote,
  onDeleteNote,
  isLoading = false,
  isSaving = false,
  leadName = 'Lead'
}: LeadNotesProps) {
  const [newNote, setNewNote] = useState('')
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')

  const handleAddNote = async () => {
    if (!newNote.trim() || !onAddNote) return
    
    try {
      await onAddNote(newNote.trim())
      setNewNote('')
    } catch (error) {
      console.error('Failed to add note:', error)
    }
  }

  const handleStartEdit = (note: Note) => {
    setEditingNoteId(note.id)
    setEditContent(note.content)
  }

  const handleCancelEdit = () => {
    setEditingNoteId(null)
    setEditContent('')
  }

  const handleSaveEdit = async (noteId: string) => {
    if (!editContent.trim() || !onEditNote) return
    
    try {
      await onEditNote(noteId, editContent.trim())
      setEditingNoteId(null)
      setEditContent('')
    } catch (error) {
      console.error('Failed to update note:', error)
    }
  }

  const handleDeleteNote = async (noteId: string) => {
    if (!onDeleteNote) return
    
    if (!confirm('Are you sure you want to delete this note?')) return
    
    try {
      await onDeleteNote(noteId)
    } catch (error) {
      console.error('Failed to delete note:', error)
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Notes</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-4">
            <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            <div className="text-muted-foreground">Loading notes...</div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Notes</CardTitle>
          <Badge variant="outline" className="px-2 py-1 text-xs">
            {notes.length} {notes.length === 1 ? 'note' : 'notes'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Add Note Form */}
        <div className="space-y-3">
          <Textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder={`Add a note about ${leadName}...`}
            className="min-h-[80px] resize-none"
            disabled={isSaving}
          />
          <div className="flex justify-between">
            <div className="text-xs text-muted-foreground">
              {newNote.length}/2000
            </div>
            <Button
              onClick={handleAddNote}
              disabled={!newNote.trim() || isSaving}
              size="sm"
            >
              {isSaving ? (
                <Icons.RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Icons.Plus className="mr-2 h-4 w-4" />
                  Add Note
                </>
              )}
            </Button>
          </div>
        </div>

        <Separator />

        {/* Notes List */}
        {notes.length === 0 ? (
          <div className="text-center py-8">
            <Icons.FileText className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <div className="text-muted-foreground">No notes yet</div>
            <div className="text-sm text-muted-foreground mt-1">
              Add notes to track important information about this lead
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {notes.map((note) => (
              <div
                key={note.id}
                className="border rounded-lg p-4 hover:bg-muted/50 transition-colors"
              >
                {editingNoteId === note.id ? (
                  <div className="space-y-3">
                    <Textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      className="min-h-[100px]"
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleCancelEdit}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => handleSaveEdit(note.id)}
                        disabled={!editContent.trim() || isSaving}
                      >
                        Save Changes
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="mb-3">
                      <div className="text-sm whitespace-pre-wrap">{note.content}</div>
                    </div>
                    
                    <div className="flex justify-between items-center">
                      <div className="text-xs text-muted-foreground">
                        <span className="font-medium">{note.createdBy}</span>
                        <span className="mx-2">•</span>
                        <span>{formatDistanceToNow(new Date(note.createdAt), { addSuffix: true })}</span>
                        {note.updatedAt && note.updatedAt !== note.createdAt && (
                          <>
                            <span className="mx-2">•</span>
                            <span>Edited {formatDistanceToNow(new Date(note.updatedAt), { addSuffix: true })}</span>
                          </>
                        )}
                      </div>
                      
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleStartEdit(note)}
                          className="h-6 px-2"
                        >
                          <Icons.Edit className="h-3 w-3" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleDeleteNote(note.id)}
                          className="h-6 px-2 text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Icons.Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}