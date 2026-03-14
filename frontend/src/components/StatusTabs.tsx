interface StatusTabsProps {
  statuses: Array<string | null>;
  current: string | null;
  onChange: (status: string | null) => void;
  formatLabel?: (status: string | null) => string;
}

function defaultLabel(status: string | null): string {
  if (!status) return 'All';
  return status.replace(/_/g, ' ');
}

export function StatusTabs({
  statuses,
  current,
  onChange,
  formatLabel = defaultLabel,
}: StatusTabsProps) {
  return (
    <div class="tabs">
      {statuses.map((s) => (
        <button
          key={s}
          class={`tab ${current === s ? 'active' : ''}`}
          onClick={() => onChange(s)}
        >
          {formatLabel(s)}
        </button>
      ))}
    </div>
  );
}
