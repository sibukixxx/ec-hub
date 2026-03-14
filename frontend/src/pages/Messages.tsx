import type { RoutableProps } from 'preact-router';
import { useEffect, useState } from 'preact/hooks';
import { api } from '../api';
import { Alerts } from '../components/Alerts';
import { Badge } from '../components/Badge';
import { EmptyRow } from '../components/EmptyRow';
import { inputValue } from '../lib/format';
import type { Message } from '../types';

export function Messages(_props: RoutableProps) {
  const [buyer, setBuyer] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [sendingId, setSendingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = async (buyerFilter = buyer) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getMessages(
        buyerFilter.trim() || undefined,
        100
      );
      setMessages(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load('');
  }, []);

  const reply = async (messageId: number) => {
    const body = (drafts[messageId] || '').trim();
    if (!body) return;

    setSendingId(messageId);
    setError(null);
    setNotice(null);
    try {
      await api.replyMessage(messageId, body);
      setDrafts((current) => ({ ...current, [messageId]: '' }));
      setNotice(`Reply sent for message #${messageId}.`);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSendingId(null);
    }
  };

  return (
    <div>
      <h2 class="page-title">Messages</h2>

      <div class="card" style="margin-bottom:1.5rem">
        <div class="toolbar">
          <div class="field grow">
            <label>Buyer Filter</label>
            <input
              type="text"
              value={buyer}
              onInput={(e) => setBuyer(inputValue(e))}
              placeholder="buyer username"
            />
          </div>
          <button class="btn btn-primary" onClick={() => load()}>
            Refresh
          </button>
        </div>
      </div>

      <Alerts notice={notice} error={error} />

      {loading ? (
        <div class="loading">Loading...</div>
      ) : (
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Buyer</th>
                <th>Direction</th>
                <th>Order</th>
                <th>Listing</th>
                <th>Candidate</th>
                <th>Category</th>
                <th>Body</th>
                <th>Reply</th>
              </tr>
            </thead>
            <tbody>
              {messages.map((msg) => (
                <tr key={msg.id}>
                  <td>{msg.id}</td>
                  <td>{msg.buyer_username}</td>
                  <td>
                    <Badge
                      status={msg.direction}
                      class={
                        msg.direction === 'outbound'
                          ? 'approved'
                          : 'awaiting_purchase'
                      }
                    />
                  </td>
                  <td>{msg.order_ebay_order_id || msg.order_id || '-'}</td>
                  <td>{msg.listing_sku || msg.listing_id || '-'}</td>
                  <td>{msg.candidate_item_code || msg.candidate_id || '-'}</td>
                  <td>{msg.category || '-'}</td>
                  <td style="min-width:220px;white-space:pre-wrap">
                    {msg.body}
                  </td>
                  <td style="min-width:240px">
                    {msg.direction === 'inbound' ? (
                      <div class="stack">
                        <textarea
                          rows={3}
                          value={drafts[msg.id] || ''}
                          onInput={(e) =>
                            setDrafts((current) => ({
                              ...current,
                              [msg.id]: inputValue(e),
                            }))
                          }
                          placeholder="Write a manual reply"
                        />
                        <button
                          class="btn btn-primary btn-sm"
                          onClick={() => reply(msg.id)}
                          disabled={
                            sendingId === msg.id ||
                            !(drafts[msg.id] || '').trim()
                          }
                        >
                          {sendingId === msg.id ? 'Sending...' : 'Reply'}
                        </button>
                      </div>
                    ) : (
                      <span class="muted">Already sent</span>
                    )}
                  </td>
                </tr>
              ))}
              {messages.length === 0 && (
                <EmptyRow colspan={9} message="No messages found" />
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
