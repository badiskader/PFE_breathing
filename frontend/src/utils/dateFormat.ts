export function formatHour(timestamp: string) {
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    hour12: true,
    timeZone: 'UTC',
  })
    .format(new Date(timestamp))
    .replace(' ', ' ');
}

export function formatDashboardDate(timestamp: string) {
  const date = new Date(timestamp);
  const time = new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    hour12: true,
    minute: '2-digit',
    timeZone: 'UTC',
  }).format(date);
  const day = new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
    weekday: 'short',
  }).format(date);

  return `${time} · ${day}`;
}
