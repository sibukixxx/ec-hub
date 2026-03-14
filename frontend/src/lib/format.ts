/** Format a number as JPY (e.g. "¥12,345") */
export function formatJpy(value: number | null | undefined): string {
  if (value == null) return '-';
  return `\u00a5${value.toLocaleString()}`;
}

/** Format a number as USD (e.g. "$12.34") */
export function formatUsd(value: number | null | undefined): string {
  if (value == null) return '-';
  return `$${value.toFixed(2)}`;
}

/** Truncate a string with ellipsis */
export function truncate(
  text: string | null | undefined,
  maxLen: number
): string {
  if (!text) return '-';
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen)}...`;
}

/** Format an ISO timestamp to "YYYY-MM-DD HH:MM" */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '-';
  return iso.replace('T', ' ').slice(0, 16);
}

/** Format an ISO date to "YYYY-MM-DD" */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '-';
  return iso.slice(0, 10);
}

/** Extract value from an input/textarea event target */
export function inputValue(e: Event): string {
  return (e.target as HTMLInputElement | HTMLTextAreaElement).value;
}
