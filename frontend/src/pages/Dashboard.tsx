import { useQuery } from '@tanstack/react-query';
import type { RoutableProps } from 'preact-router';
import { api } from '../api';
import { formatJpy } from '../lib/format';
import { queryKeys } from '../lib/query-keys';
import type { DashboardData, ServiceHealth } from '../types';

export function Dashboard(_props: RoutableProps) {
  const { data, error, isLoading } = useQuery<DashboardData, Error>({
    queryKey: queryKeys.dashboard,
    queryFn: () => api.getDashboard(),
  });

  if (error) return <div class="loading">Error: {error.message}</div>;
  if (isLoading || !data) return <div class="loading">Loading...</div>;

  const { candidates, orders, recent_profit, fx_rate, health = [] } = data;
  const exchangeRateHealth = health.find(
    (s: ServiceHealth) => s.service_name === 'exchange_rate'
  );
  const exchangeRateWarning =
    exchangeRateHealth && exchangeRateHealth.status !== 'ok'
      ? exchangeRateHealth
      : null;

  return (
    <div>
      <h2 class="page-title">Dashboard</h2>

      {exchangeRateWarning && (
        <div class="alert alert-warning">
          <strong>Exchange rate fallback in use.</strong>
          <div>
            {exchangeRateWarning.error_message ||
              'Using a degraded exchange rate source.'}
          </div>
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
