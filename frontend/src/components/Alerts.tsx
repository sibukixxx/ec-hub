interface AlertsProps {
  notice?: string | null;
  error?: string | null;
}

export function Alerts({ notice, error }: AlertsProps) {
  return (
    <>
      {notice && <div class="alert alert-success">{notice}</div>}
      {error && <div class="alert alert-danger">{error}</div>}
    </>
  );
}
