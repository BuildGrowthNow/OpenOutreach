/**
 * Normalize deal state from backend format to frontend format
 * Backend sends Title Case with spaces: "Qualified", "Ready to Connect"
 * Frontend uses UPPERCASE_SNAKE_CASE: "QUALIFIED", "READY_TO_CONNECT"
 */
export function normalizeState(state: string | null | undefined): string | null {
  if (!state) return null;
  
  const stateMap: Record<string, string> = {
    'Qualified': 'QUALIFIED',
    'Ready to Connect': 'READY_TO_CONNECT',
    'Pending': 'PENDING',
    'Connected': 'CONNECTED',
    'Completed': 'COMPLETED',
    'Failed': 'FAILED',
    'No Email': 'NO_EMAIL',
  };
  
  return stateMap[state] || state;
}

/**
 * Normalize deal outcome from backend format to frontend format
 */
export function normalizeOutcome(outcome: string | null | undefined): string | null {
  if (!outcome) return null;
  // Outcomes are already in snake_case format from the backend
  return outcome;
}
