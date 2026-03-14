/** Return CSS color for a margin rate (0.0-1.0 scale) */
export function marginColor(rate: number): string {
  if (rate >= 0.3) return 'var(--green)';
  if (rate >= 0.15) return 'var(--yellow)';
  return 'var(--red)';
}

/** Return CSS color for a match score (0-100 scale) */
export function matchScoreColor(score: number): string {
  if (score >= 60) return 'var(--green)';
  if (score >= 40) return 'var(--yellow)';
  return 'var(--text-dim)';
}

/** Return CSS color for a profit/loss value */
export function profitColor(value: number): string {
  return value >= 0 ? 'var(--green)' : 'var(--red)';
}

/** Map a running/completed boolean to a badge CSS class */
export function runStatusBadge(completed: boolean): string {
  return completed ? 'completed' : 'awaiting_purchase';
}

/** Map a health status to a badge CSS class */
export function healthBadge(status: string): string {
  if (status === 'ok') return 'approved';
  if (status === 'degraded') return 'awaiting_purchase';
  return 'rejected';
}
