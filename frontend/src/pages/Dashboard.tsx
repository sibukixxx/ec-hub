import { useQuery } from '@tanstack/react-query';
import type { RoutableProps } from 'preact-router';
import { Badge } from '../components/Badge';
import { api } from '../api';
import { formatJpy, formatTimestamp } from '../lib/format';
import { queryKeys } from '../lib/query-keys';
import type { DashboardData, JobRun, ServiceHealth } from '../types';

export function Dashboard(_props: RoutableProps) {
  const { data, error, isLoading } = useQuery<DashboardData, Error>({
    queryKey: queryKeys.dashboard,
    queryFn: () => api.getDashboard(),
  });

  if (error) return <div class="loading">Error: {error.message}</div>;
  if (isLoading || !data) return <div class="loading">Loading...</div>;

  const {
    candidates,
    orders,
    recent_profit,
    fx_rate,
    health = [],
    recent_jobs = [],
  } = data;

  const degradedServices = health.filter(
    (s: ServiceHealth) => s.status !== 'ok' && s.status !== 'unknown'
  );
  const failedJobs = recent_jobs.filter(
    (j: JobRun) => j.status === 'failed'
  );

  return (
    <div>
      <h2 class="page-title">Dashboard</h2>

      {degradedServices.length > 0 && (
        <div class="alert alert-warning">
          <strong>Service alerts</strong>
          <ul style={{ margin: '4px 0 0', paddingLeft: '20px' }}>
            {degradedServices.map((s) => (
              <li key={s.service_name}>
                <strong>{s.service_name}</strong>: {s.status}
                {s.error_message && ` — ${s.error_message}`}
              </li>
            ))}
          </ul>
        </div>
      )}

      {failedJobs.length > 0 && (
        <div class="alert alert-error">
          <strong>Recent job failures</strong>
          <ul style={{ margin: '4px 0 0', paddingLeft: '20px' }}>
            {failedJobs.map((j) => (
              <li key={j.id}>
                <strong>{j.job_name}</strong> failed at{' '}
                {formatTimestamp(j.started_at)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div class="cards">
        <MetricCard
          label="Pending Candidates"
          value={candidates.pending}
          color="blue"
        />
        <MetricCard
          label="Approved"
          value={candidates.approved}
          color="green"
        />
        <MetricCard label="Listed on eBay" value={candidates.listed} />
        <MetricCard
          label="Active Orders"
          value={orders.awaiting_purchase + orders.shipped}
          color="blue"
        />
        <MetricCard
          label="Completed Orders"
          value={orders.completed}
          color="green"
        />
        <div class="card">
          <div class="label">Total Profit</div>
          <div class={`value ${recent_profit >= 0 ? 'green' : 'red'}`}>
            {formatJpy(recent_profit)}
          </div>
        </div>
        <MetricCard label="USD/JPY Rate" value={fx_rate.toFixed(2)} />
      </div>

      {recent_jobs.length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <h3>Recent Jobs</h3>
          <table class="table">
            <thead>
              <tr>
                <th>Job</th>
                <th>Status</th>
                <th>Items</th>
                <th>Started</th>
              </tr>
            </thead>
            <tbody>
              {recent_jobs.map((run) => (
                <tr key={run.id}>
                  <td>{run.job_name}</td>
                  <td>
                    <Badge status={run.status} />
                  </td>
                  <td>{run.items_processed}</td>
                  <td>{formatTimestamp(run.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: number | string;
  color?: 'blue' | 'green' | 'red';
}

function MetricCard({ label, value, color }: MetricCardProps) {
  return (
    <div class="card">
      <div class="label">{label}</div>
      <div class={`value ${color || ''}`}>{value}</div>
    </div>
  );
}
