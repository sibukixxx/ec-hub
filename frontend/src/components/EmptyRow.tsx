interface EmptyRowProps {
  colspan: number;
  message: string;
}

export function EmptyRow({ colspan, message }: EmptyRowProps) {
  return (
    <tr>
      <td colspan={colspan} style="text-align:center;color:var(--text-muted)">
        {message}
      </td>
    </tr>
  );
}
