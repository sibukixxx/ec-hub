import type { RoutableProps } from 'preact-router';
import { useState, useEffect } from 'preact/hooks';
import { api } from '../api';
import { Alerts } from '../components/Alerts';
import { Badge } from '../components/Badge';
import { EmptyRow } from '../components/EmptyRow';
import { StatusTabs } from '../components/StatusTabs';
import { formatDate, formatJpy, formatUsd, inputValue } from '../lib/format';
import type { Order } from '../types';

const STATUSES: Array<string | null> = [
  null,
  'awaiting_purchase',
  'purchased',
  'shipped',
  'delivered',
  'completed',
];

interface OrderDrafts {
  [orderId: number]: {
    actual_cost_jpy?: string;
    tracking_number?: string;
    shipping_cost_jpy?: string;
  };
}

export function Orders(_props: RoutableProps) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [filter, setFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<OrderDrafts>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getOrders(filter, 100);
      setOrders(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [filter]);

  const updateDraft = (orderId: number, key: string, value: string) => {
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
      setNotice(
        `Order sync completed: ${result.new_orders} new orders registered.`
      );
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSyncing(false);
    }
  };

  const updateStatus = async (order: Order, status: string) => {
    const draft = drafts[order.id] || {};
    const payload: Record<string, unknown> = { status };

    if (status === 'purchased') {
      payload.actual_cost_jpy = Number(draft.actual_cost_jpy || 0);
    }
    if (status === 'shipped') {
      payload.tracking_number = (draft.tracking_number || '').trim();
      payload.shipping_cost_jpy = Number(draft.shipping_cost_jpy || 0);
      if (!payload.tracking_number) {
        setError(
          'Tracking number is required before marking an order as shipped.'
        );
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
      setError((e as Error).message);
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div>
      <h2 class="page-title">Orders</h2>

      <div class="toolbar" style="margin-bottom:1rem">
        <button
          class="btn btn-primary"
          onClick={checkOrders}
          disabled={syncing}
        >
          {syncing ? 'Syncing...' : 'Check New Orders'}
        </button>
        <a class="btn btn-secondary" href={api.exportUrl('orders', 'csv')}>
          Export CSV
        </a>
        <a class="btn btn-secondary" href={api.exportUrl('orders', 'json')}>
          Export JSON
        </a>
      </div>

      <Alerts notice={notice} error={error} />

      <StatusTabs statuses={STATUSES} current={filter} onChange={setFilter} />

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
                  <td>{formatUsd(o.sale_price_usd || 0)}</td>
                  <td>{formatJpy(o.actual_cost_jpy)}</td>
                  <td>{formatJpy(o.net_profit_jpy)}</td>
                  <td>{o.destination_country || '-'}</td>
                  <td>{o.tracking_number || '-'}</td>
                  <td>
                    <Badge status={o.status} />
                  </td>
                  <td>{formatDate(o.ordered_at)}</td>
                  <td style="min-width:230px">
                    <OrderActions
                      order={o}
                      drafts={drafts}
                      updatingId={updatingId}
                      onDraftChange={updateDraft}
                      onStatusChange={updateStatus}
                    />
                  </td>
                </tr>
              ))}
              {orders.length === 0 && (
                <EmptyRow colspan={11} message="No orders found" />
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface OrderActionsProps {
  order: Order;
  drafts: OrderDrafts;
  updatingId: number | null;
  onDraftChange: (id: number, key: string, value: string) => void;
  onStatusChange: (order: Order, status: string) => void;
}

function OrderActions({
  order: o,
  drafts,
  updatingId,
  onDraftChange,
  onStatusChange,
}: OrderActionsProps) {
  const busy = updatingId === o.id;
  const busyLabel = busy ? 'Updating...' : null;

  if (o.status === 'awaiting_purchase') {
    return (
      <div class="stack">
        <input
          type="number"
          value={drafts[o.id]?.actual_cost_jpy || ''}
          onInput={(e) => onDraftChange(o.id, 'actual_cost_jpy', inputValue(e))}
          placeholder="Actual cost (JPY)"
        />
        <button
          class="btn btn-primary btn-sm"
          onClick={() => onStatusChange(o, 'purchased')}
          disabled={busy}
        >
          {busyLabel || 'Mark Purchased'}
        </button>
      </div>
    );
  }

  if (o.status === 'purchased') {
    return (
      <div class="stack">
        <input
          type="text"
          value={drafts[o.id]?.tracking_number || ''}
          onInput={(e) => onDraftChange(o.id, 'tracking_number', inputValue(e))}
          placeholder="Tracking number"
        />
        <input
          type="number"
          value={drafts[o.id]?.shipping_cost_jpy || ''}
          onInput={(e) =>
            onDraftChange(o.id, 'shipping_cost_jpy', inputValue(e))
          }
          placeholder="Shipping cost (JPY)"
        />
        <button
          class="btn btn-primary btn-sm"
          onClick={() => onStatusChange(o, 'shipped')}
          disabled={busy}
        >
          {busyLabel || 'Mark Shipped'}
        </button>
      </div>
    );
  }

  if (o.status === 'shipped') {
    return (
      <button
        class="btn btn-primary btn-sm"
        onClick={() => onStatusChange(o, 'delivered')}
        disabled={busy}
      >
        {busyLabel || 'Mark Delivered'}
      </button>
    );
  }

  if (o.status === 'delivered') {
    return (
      <button
        class="btn btn-success btn-sm"
        onClick={() => onStatusChange(o, 'completed')}
        disabled={busy}
      >
        {busyLabel || 'Complete Order'}
      </button>
    );
  }

  if (o.status === 'completed') {
    return <span class="muted">Done</span>;
  }

  return null;
}
