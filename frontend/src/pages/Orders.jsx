import { useState, useEffect } from 'preact/hooks';
import { api } from '../api';

const STATUSES = [null, 'awaiting_purchase', 'purchased', 'shipped', 'delivered', 'completed'];

export function Orders() {
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [updatingId, setUpdatingId] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getOrders(filter, 100);
      setOrders(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [filter]);

  const updateDraft = (orderId, key, value) => {
    setDrafts((current) => ({
      ...current,
      [orderId]: { ...(current[orderId] || {}), [key]: value },
    }));
  };

  const checkOrders = async () => {
    setSyncing(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.checkOrders();
      setNotice(`Order sync completed: ${result.new_orders} new orders registered.`);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSyncing(false);
    }
  };

  const updateStatus = async (order, status) => {
    const draft = drafts[order.id] || {};
    const payload = { status };

    if (status === 'purchased') {
      payload.actual_cost_jpy = Number(draft.actual_cost_jpy || 0);
    }
    if (status === 'shipped') {
      payload.tracking_number = (draft.tracking_number || '').trim();
      payload.shipping_cost_jpy = Number(draft.shipping_cost_jpy || 0);
      if (!payload.tracking_number) {
        setError('Tracking number is required before marking an order as shipped.');
        return;
      }
    }

    setUpdatingId(order.id);
    setError(null);
    setNotice(null);
    try {
      await api.updateOrderStatus(order.id, payload);
      setNotice(`Order #${order.id} updated to ${status}.`);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div>
      <h2 class="page-title">Orders</h2>

      <div class="toolbar" style="margin-bottom:1rem">
        <button class="btn btn-primary" onClick={checkOrders} disabled={syncing}>
          {syncing ? 'Syncing...' : 'Check New Orders'}
        </button>
        <a class="btn btn-secondary" href={api.exportUrl('orders', 'csv')}>Export CSV</a>
        <a class="btn btn-secondary" href={api.exportUrl('orders', 'json')}>Export JSON</a>
      </div>

      {notice && <div class="alert alert-success">{notice}</div>}
      {error && <div class="alert alert-danger">{error}</div>}

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
                <th>Actions</th>
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
                  <td style="min-width:230px">
                    {o.status === 'awaiting_purchase' && (
                      <div class="stack">
                        <input
                          type="number"
                          value={drafts[o.id]?.actual_cost_jpy || ''}
                          onInput={(e) => updateDraft(o.id, 'actual_cost_jpy', e.target.value)}
                          placeholder="Actual cost (JPY)"
                        />
                        <button
                          class="btn btn-primary btn-sm"
                          onClick={() => updateStatus(o, 'purchased')}
                          disabled={updatingId === o.id}
                        >
                          {updatingId === o.id ? 'Updating...' : 'Mark Purchased'}
                        </button>
                      </div>
                    )}
                    {o.status === 'purchased' && (
                      <div class="stack">
                        <input
                          type="text"
                          value={drafts[o.id]?.tracking_number || ''}
                          onInput={(e) => updateDraft(o.id, 'tracking_number', e.target.value)}
                          placeholder="Tracking number"
                        />
                        <input
                          type="number"
                          value={drafts[o.id]?.shipping_cost_jpy || ''}
                          onInput={(e) => updateDraft(o.id, 'shipping_cost_jpy', e.target.value)}
                          placeholder="Shipping cost (JPY)"
                        />
                        <button
                          class="btn btn-primary btn-sm"
                          onClick={() => updateStatus(o, 'shipped')}
                          disabled={updatingId === o.id}
                        >
                          {updatingId === o.id ? 'Updating...' : 'Mark Shipped'}
                        </button>
                      </div>
                    )}
                    {o.status === 'shipped' && (
                      <button
                        class="btn btn-primary btn-sm"
                        onClick={() => updateStatus(o, 'delivered')}
                        disabled={updatingId === o.id}
                      >
                        {updatingId === o.id ? 'Updating...' : 'Mark Delivered'}
                      </button>
                    )}
                    {o.status === 'delivered' && (
                      <button
                        class="btn btn-success btn-sm"
                        onClick={() => updateStatus(o, 'completed')}
                        disabled={updatingId === o.id}
                      >
                        {updatingId === o.id ? 'Updating...' : 'Complete Order'}
                      </button>
                    )}
                    {o.status === 'completed' && <span class="muted">Done</span>}
                  </td>
                </tr>
              ))}
              {orders.length === 0 && (
                <tr><td colspan="11" style="text-align:center;color:var(--text-muted)">No orders found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
