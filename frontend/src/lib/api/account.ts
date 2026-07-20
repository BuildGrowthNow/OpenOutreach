/**
 * Account lifecycle API - deletion, recovery, data export
 */

const API_BASE = '/api'

export async function requestAccountDeletion(accessToken: string) {
  const response = await fetch(`${API_BASE}/auth/account/request-deletion/`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to request account deletion')
  }

  return response.json()
}

export async function cancelAccountDeletion(accessToken: string) {
  const response = await fetch(`${API_BASE}/auth/account/cancel-deletion/`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to cancel account deletion')
  }

  return response.json()
}

export async function exportUserData(accessToken: string) {
  const response = await fetch(`${API_BASE}/auth/account/export-data/`, {
    method: 'GET',
    credentials: 'include',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to export data')
  }

  return response.json()
}

export async function downloadUserDataAsJSON(accessToken: string) {
  const data = await exportUserData(accessToken)

  const dataStr = JSON.stringify(data, null, 2)
  const dataBlob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(dataBlob)
  const link = document.createElement('a')
  link.href = url
  link.download = `lengrowth-data-export-${new Date().toISOString().split('T')[0]}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
