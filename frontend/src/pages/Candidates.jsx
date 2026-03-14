import { useState, useEffect } from 'preact/hooks';
import { api } from '../api';

const STATUSES = [null, 'pending', 'approved', 'rejected', 'listed'];

export function Candidates() {
  const [candidates, setCandidates] = useState([]);
  const [filter, setFilter] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.getCandidates(filter, 100).then(setCandidates).finally(() => setLoading(false));
  };

  useEffect(load, [filter]);

  const updateStatus = async (id, status) => {
    await api.updateCandidateStatus(id, status);
    load();
  };

  return (
    <div>
      <h2 class="page-title">Candidates</h2>

      <div class="tabs">
        {STATUSES.map((s) => (
          <button
            key={s}
            class={`tab ${filter === s ? 'active' : ''}`}
            onClick={() => setFilter(s)}
          >
            {s || 'All'}
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
                <th>Title</th>
                <th>Source</th>
                <th>eBay Origin</th>
                <th>Cost</th>
                <th>eBay Price</th>
                <th>Profit</th>
                <th>Margin</th>
                <th>Match</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td title={c.title_jp}>{(c.title_jp || '').slice(0, 35)}</td>
                  <td>{c.source_site}</td>
                  <td>
                    {c.ebay_title ? (
                      c.ebay_url ? (
                        <a href={c.ebay_url} target="_blank" rel="noopener noreferrer" title={c.ebay_title}>
                          {c.ebay_title.slice(0, 30)}
                        </a>
                      ) : (
                        <span title={c.ebay_title}>{c.ebay_title.slice(0, 30)}</span>
                      )
                    ) : '-'}
                  </td>
                  <td>{'\u00a5'}{(c.cost_jpy || 0).toLocaleString()}</td>
                  <td>${(c.ebay_price_usd || 0).toFixed(2)}</td>
                  <td class={c.net_profit_jpy > 0 ? '' : ''}>
                    {c.net_profit_jpy != null ? `\u00a5${c.net_profit_jpy.toLocaleString()}` : '-'}
                  </td>
                  <td>
                    {c.margin_rate != null ? `${(c.margin_rate * 100).toFixed(0)}%` : '-'}
                  </td>
                  <td style={`font-weight:700;color:${(c.match_score ?? 0) >= 60 ? 'var(--green)' : (c.match_score ?? 0) >= 40 ? 'var(--yellow)' : 'var(--text-dim)'}`}>
                    {c.match_score != null ? `${c.match_score}/100` : '-'}
                  </td>
                  <td title={c.match_reason || ''} style="max-width:280px;color:var(--text-dim);font-size:0.85rem">
                    {c.match_reason ? `${c.match_reason.slice(0, 72)}${c.match_reason.length > 72 ? '...' : ''}` : '-'}
                  </td>
                  <td><span class={`badge ${c.status}`}>{c.status}</span></td>
                  <td>
                    {c.status === 'pending' && (
                      <>
                        <button class="btn btn-success btn-sm" onClick={() => updateStatus(c.id, 'approved')}>
                          Approve
                        </button>{' '}
                        <button class="btn btn-danger btn-sm" onClick={() => updateStatus(c.id, 'rejected')}>
                          Reject
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {candidates.length === 0 && (
                <tr><td colspan="12" style="text-align:center;color:var(--text-muted)">No candidates found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
