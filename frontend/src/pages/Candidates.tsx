import type { RoutableProps } from 'preact-router';
import { useState, useEffect } from 'preact/hooks';
import { api } from '../api';
import { Badge } from '../components/Badge';
import { EmptyRow } from '../components/EmptyRow';
import { StatusTabs } from '../components/StatusTabs';
import { matchScoreColor } from '../lib/color';
import { formatJpy, formatUsd, truncate } from '../lib/format';
import type { Candidate } from '../types';

const STATUSES: Array<string | null> = [
  null,
  'pending',
  'approved',
  'rejected',
  'listed',
];

export function Candidates(_props: RoutableProps) {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [filter, setFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    void api
      .getCandidates(filter, 100)
      .then(setCandidates)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, [filter]);

  const updateStatus = async (id: number, status: string) => {
    await api.updateCandidateStatus(id, status);
    load();
  };

  return (
    <div>
      <h2 class="page-title">Candidates</h2>

      <StatusTabs statuses={STATUSES} current={filter} onChange={setFilter} />

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
                  <td title={c.title_jp || ''}>{truncate(c.title_jp, 35)}</td>
                  <td>{c.source_site}</td>
                  <td>
                    <EbayOriginCell title={c.ebay_title} url={c.ebay_url} />
                  </td>
                  <td>{formatJpy(c.cost_jpy || 0)}</td>
                  <td>{formatUsd(c.ebay_price_usd || 0)}</td>
                  <td>{formatJpy(c.net_profit_jpy)}</td>
                  <td>
                    {c.margin_rate != null
                      ? `${(c.margin_rate * 100).toFixed(0)}%`
                      : '-'}
                  </td>
                  <td
                    style={`font-weight:700;color:${matchScoreColor(c.match_score ?? 0)}`}
                  >
                    {c.match_score != null ? `${c.match_score}/100` : '-'}
                  </td>
                  <td
                    title={c.match_reason || ''}
                    style="max-width:280px;color:var(--text-dim);font-size:0.85rem"
                  >
                    {truncate(c.match_reason, 72)}
                  </td>
                  <td>
                    <Badge status={c.status} />
                  </td>
                  <td>
                    {c.status === 'pending' && (
                      <>
                        <button
                          class="btn btn-success btn-sm"
                          onClick={() => updateStatus(c.id, 'approved')}
                        >
                          Approve
                        </button>{' '}
                        <button
                          class="btn btn-danger btn-sm"
                          onClick={() => updateStatus(c.id, 'rejected')}
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {candidates.length === 0 && (
                <EmptyRow colspan={12} message="No candidates found" />
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function EbayOriginCell({
  title,
  url,
}: {
  title: string | null;
  url: string | null;
}) {
  if (!title) return <>-</>;
  const text = title.slice(0, 30);
  if (url) {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" title={title}>
        {text}
      </a>
    );
  }
  return <span title={title}>{text}</span>;
}
