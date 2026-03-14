interface BadgeProps {
  status: string;
  class?: string;
}

export function Badge({ status, class: extraClass }: BadgeProps) {
  const cls = extraClass ? `badge ${extraClass}` : `badge ${status}`;
  return <span class={cls}>{status}</span>;
}
