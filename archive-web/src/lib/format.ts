export function formatNumber(value: number | undefined): string {
  return (value ?? 0).toLocaleString();
}

export function initials(value: string): string {
  const words = value.trim().split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? 'W') + (words[1]?.[0] ?? '')).toUpperCase();
}

export function relativeDate(value: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function statusLabel(status: string): string {
  return status.replace(/_/g, ' ');
}
