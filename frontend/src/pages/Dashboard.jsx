import { useState, useEffect } from 'preact/hooks';
import { api } from '../api';

export function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getDashboard().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div class="loading">Error: {error}</div>;
  if (!data) return <div class="loading">Loading...</div>;

  const { candidates, orders, recent_profit, fx_rate } = data;

  return (
    <div>
      <h2 class="page-title">Dashboard</h2>

      <div class="cards">
        <div class="card">
          <div class="label">Pending Candidates</div>
          <div class="value blue">{candidates.pending}</div>
        </div>
        <div class="card">
          <div class="label">Approved</div>
          <div class="value green">{candidates.approved}</div>
        </div>
        <div class="card">
          <div class="label">Listed on eBay</div>
          <div class="value">{candidates.listed}</div>
        </div>
        <div class="card">
          <div class="label">Active Orders</div>
          <div class="value blue">{orders.awaiting_purchase + orders.shipped}</div>
        </div>
        <div class="card">
          <div class="label">Completed Orders</div>
          <div class="value green">{orders.completed}</div>
        </div>
        <div class="card">
          <div class="label">Total Profit</div>
          <div class={`value ${recent_profit >= 0 ? 'green' : 'red'}`}>
            {'\u00a5'}{recent_profit.toLocaleString()}
          </div>
        </div>
        <div class="card">
          <div class="label">USD/JPY Rate</div>
          <div class="value">{fx_rate.toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
}
