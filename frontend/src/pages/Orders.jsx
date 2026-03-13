import { useState, useEffect } from 'preact/hooks';
import { api } from '../api';

const STATUSES = [null, 'awaiting_purchase', 'purchased', 'shipped', 'delivered', 'completed'];

export function Orders() {
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getOrders(filter, 100).then(setOrders).finally(() => setLoading(false));
  }, [filter]);

  return (
    <div>
      <h2 class="page-title">Orders</h2>

      <div class="tabs">
        {STATUSES.map((s) => (
          <button
            key={s}
            class={`tab ${filter === s ? 'active' : ''}`}
            onClick={() => setFilter(s)}
          >
            {s ? s.replace('_', ' ') : 'All'}
          </button>
        ))}
      </div>

      {loading ? (
        <div class="loading">Loading...</div>
      ) : (
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>eBay Order</th>
                <th>Buyer</th>
                <th>Sale Price</th>
                <th>Cost</th>
                <th>Profit</th>
                <th>Dest</th>
                <th>Tracking</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>{o.id}</td>
                  <td>{(o.ebay_order_id || '').slice(0, 16)}</td>
                  <td>{o.buyer_username || '-'}</td>
                  <td>${(o.sale_price_usd || 0).toFixed(2)}</td>
                  <td>
                    {o.actual_cost_jpy != null ? `\u00a5${o.actual_cost_jpy.toLocaleString()}` : '-'}
                  </td>
                  <td>
                    {o.net_profit_jpy != null ? `\u00a5${o.net_profit_jpy.toLocaleString()}` : '-'}
                  </td>
                  <td>{o.destination_country || '-'}</td>
                  <td>{o.tracking_number || '-'}</td>
                  <td><span class={`badge ${o.status}`}>{o.status}</span></td>
                  <td>{(o.ordered_at || '').slice(0, 10)}</td>
                </tr>
              ))}
              {orders.length === 0 && (
                <tr><td colspan="10" style="text-align:center;color:var(--text-muted)">No orders found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
