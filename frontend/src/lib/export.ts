'use client'

import { Lead } from '@/lib/types/components'

/**
 * Convert leads data to CSV format
 */
export function convertLeadsToCSV(leads: Lead[]): string {
  if (leads.length === 0) {
    return ''
  }

  const headers = [
    'ID',
    'Name',
    'Email',
    'LinkedIn URL',
    'Company',
    'Title',
    'Status',
    'Outcome',
    'Disqualified',
    'Created At',
    'Updated At',
    'Phone Numbers',
    'Messages Count',
    'Last Message At'
  ]

  const rows = leads.map(lead => {
    const phoneNumbers = lead.contactInfo?.phoneNumbers?.join('; ') || ''
    
    const escapeCSV = (value: unknown): string => {
      if (value === null || value === undefined) return ''
      const stringValue = String(value)
      // Escape quotes and wrap in quotes if contains comma, quote, or newline
      if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
        return `"${stringValue.replace(/"/g, '""')}"`
      }
      return stringValue
    }

    return [
      escapeCSV(lead.id),
      escapeCSV(lead.name),
      escapeCSV(lead.contactInfo?.email),
      escapeCSV(lead.linkedinUrl),
      escapeCSV(lead.company),
      escapeCSV(lead.title),
      escapeCSV(lead.state),
      escapeCSV(lead.outcome),
      escapeCSV(lead.disqualified ? 'Yes' : 'No'),
      escapeCSV(new Date(lead.creationDate).toISOString()),
      escapeCSV(new Date(lead.updateDate).toISOString()),
      escapeCSV(phoneNumbers),
      escapeCSV(lead.messagesCount || 0),
      escapeCSV(lead.lastMessageAt ? new Date(lead.lastMessageAt).toISOString() : '')
    ].join(',')
  })

  return [headers.join(','), ...rows].join('\n')
}

/**
 * Download CSV file
 */
export function downloadCSV(csvContent: string, filename: string = 'leads-export.csv'): void {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  
  if (link.download !== undefined) {
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', filename)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }
}

/**
 * Export leads to CSV and trigger download
 */
export function exportLeadsToCSV(leads: Lead[], filename?: string): void {
  const csvContent = convertLeadsToCSV(leads)
  if (csvContent) {
    downloadCSV(csvContent, filename)
  }
}

/**
 * Generate filename with timestamp
 */
export function generateExportFilename(baseName: string = 'leads'): string {
  const now = new Date()
  const timestamp = now.toISOString().slice(0, 19).replace(/:/g, '-')
  return `${baseName}-${timestamp}.csv`
}

/**
 * Export current filtered leads
 */
export function exportFilteredLeads(
  leads: Lead[],
  filters: {
    status?: string
    search?: string
    disqualified?: boolean
  }
): void {
  const filterDescriptions = []
  if (filters.status && filters.status !== 'all') {
    filterDescriptions.push(`status-${filters.status}`)
  }
  if (filters.search) {
    filterDescriptions.push(`search-${filters.search.substring(0, 20)}`)
  }
  if (filters.disqualified !== undefined) {
    filterDescriptions.push(`disqualified-${filters.disqualified ? 'yes' : 'no'}`)
  }

  const filterSuffix = filterDescriptions.length > 0 
    ? `-${filterDescriptions.join('-')}` 
    : ''
  
  const filename = generateExportFilename(`leads${filterSuffix}`)
  exportLeadsToCSV(leads, filename)
}
