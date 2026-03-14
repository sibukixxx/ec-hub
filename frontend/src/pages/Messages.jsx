import { useEffect, useState } from 'preact/hooks';
import { api } from '../api';

export function Messages() {
  const [buyer, setBuyer] = useState('');
  const [messages, setMessages] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [loading, setLoading] = useState(true);
  const [sendingId, setSendingId] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = async (buyerFilter = buyer) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getMessages(buyerFilter.trim() || undefined, 100);
      setMessages(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load('');
  }, []);

  const reply = async (messageId) => {
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
      setError(e.message);
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
              onInput={(e) => setBuyer(e.target.value)}
              placeholder="buyer username"
            />
          </div>
          <button class="btn btn-primary" onClick={() => load()}>
            Refresh
          </button>
        </div>
      </div>

      {notice && <div class="alert alert-success">{notice}</div>}
      {error && <div class="alert alert-danger">{error}</div>}

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
              {messages.map((message) => (
                <tr key={message.id}>
                  <td>{message.id}</td>
                  <td>{message.buyer_username}</td>
                  <td>
                    <span class={`badge ${message.direction === 'outbound' ? 'approved' : 'awaiting_purchase'}`}>
                      {message.direction}
                    </span>
                  </td>
                  <td>{message.order_ebay_order_id || message.order_id || '-'}</td>
                  <td>{message.listing_sku || message.listing_id || '-'}</td>
                  <td>{message.candidate_item_code || message.candidate_id || '-'}</td>
                  <td>{message.category || '-'}</td>
                  <td style="min-width:220px;white-space:pre-wrap">{message.body}</td>
                  <td style="min-width:240px">
                    {message.direction === 'inbound' ? (
                      <div class="stack">
                        <textarea
                          rows="3"
                          value={drafts[message.id] || ''}
                          onInput={(e) => setDrafts((current) => ({ ...current, [message.id]: e.target.value }))}
                          placeholder="Write a manual reply"
                        />
                        <button
                          class="btn btn-primary btn-sm"
                          onClick={() => reply(message.id)}
                          disabled={sendingId === message.id || !(drafts[message.id] || '').trim()}
                        >
                          {sendingId === message.id ? 'Sending...' : 'Reply'}
                        </button>
                      </div>
                    ) : (
                      <span class="muted">Already sent</span>
                    )}
                  </td>
                </tr>
              ))}
              {messages.length === 0 && (
                <tr>
                  <td colspan="9" style="text-align:center;color:var(--text-muted)">No messages found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
