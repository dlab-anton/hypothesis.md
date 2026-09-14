export function formatRelativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;

  if (diffMs < 0) return "just now";

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;

  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;

  return `${Math.floor(months / 12)}y ago`;
}

export function formatDeadlineStatus(deadline: string): { text: string; isOverdue: boolean } {
  const now = new Date();
  const dl = new Date(deadline);
  const diffMs = dl.getTime() - now.getTime();
  const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (days < 0) {
    return { text: `Overdue by ${Math.abs(days)} day${Math.abs(days) !== 1 ? "s" : ""}`, isOverdue: true };
  }
  if (days === 0) {
    return { text: "Due today", isOverdue: false };
  }
  return { text: `${days} day${days !== 1 ? "s" : ""} remaining`, isOverdue: false };
}

export function isRecentlyUpdated(isoString: string, thresholdMinutes = 5): boolean {
  return Date.now() - new Date(isoString).getTime() < thresholdMinutes * 60 * 1000;
}
