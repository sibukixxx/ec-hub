import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { RoutableProps } from 'preact-router';
import { useState } from 'preact/hooks';
import { api } from '../api';
import { Badge } from '../components/Badge';
import { EmptyRow } from '../components/EmptyRow';
import { StatusTabs } from '../components/StatusTabs';
import { matchScoreColor } from '../lib/color';
import { formatJpy, formatUsd, truncate } from '../lib/format';
import { queryKeys } from '../lib/query-keys';
import type { Candidate } from '../types';

const STATUSES: Array<string | null> = [
  null,
  'pending',
  'approved',
  'rejected',
  'listed',
];

export function Candidates(_props: RoutableProps) {
  const [filter, setFilter] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: candidates = [], isLoading, error } = useQuery<Candidate[], Error>({
    queryKey: queryKeys.candidates(filter),
    queryFn: () => api.getCandidates(filter, 100),
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.updateCandidateStatus(id, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['candidates'] });
    },
  });

  return (
    <div>
      <h2 class="page-title">Candidates</h2>

      <StatusTabs statuses={STATUSES} current={filter} onChange={setFilter} />

      {error && <div class="loading">Error: {error.message}</div>}

      {isLoading ? (
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
                          onClick={() =>
                            updateStatusMutation.mutate({
                              id: c.id,
                              status: 'approved',
                            })
                          }
                        >
                          Approve
                        </button>{' '}
                        <button
                          class="btn btn-danger btn-sm"
                          onClick={() =>
                            updateStatusMutation.mutate({
                              id: c.id,
                              status: 'rejected',
                            })
                          }
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
