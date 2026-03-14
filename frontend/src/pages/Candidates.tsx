import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { RoutableProps } from 'preact-router';
import { useState } from 'preact/hooks';
import { api } from '../api';
import { Alerts } from '../components/Alerts';
import { Badge } from '../components/Badge';
import { EmptyRow } from '../components/EmptyRow';
import { StatusTabs } from '../components/StatusTabs';
import { matchScoreColor, profitColor } from '../lib/color';
import { formatJpy, formatUsd, truncate } from '../lib/format';
import { queryKeys } from '../lib/query-keys';
import type { Candidate, ListingPreview } from '../types';

const STATUSES: Array<string | null> = [
  null,
  'pending',
  'approved',
  'rejected',
  'listed',
];

export function Candidates(_props: RoutableProps) {
  const [filter, setFilter] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ListingPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const {
    data: candidates = [],
    isLoading,
    error: queryError,
  } = useQuery<Candidate[], Error>({
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

  const bulkMutation = useMutation({
    mutationFn: ({ ids, status }: { ids: number[]; status: string }) =>
      api.bulkUpdateCandidateStatus(ids, status),
    onMutate: () => {
      setError(null);
      setNotice(null);
    },
    onSuccess: (data) => {
      setSelected(new Set());
      setNotice(
        `${data.updated_count} candidates updated to "${data.status}".`
      );
      void queryClient.invalidateQueries({ queryKey: ['candidates'] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const publishMutation = useMutation({
    mutationFn: (candidateIds: number[]) => api.runListing(candidateIds),
    onMutate: () => {
      setError(null);
      setNotice(null);
      setPreview(null);
    },
    onSuccess: (data) => {
      setSelected(new Set());
      setNotice(`${data.listed_count} candidate(s) published to eBay.`);
      void queryClient.invalidateQueries({ queryKey: ['candidates'] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === candidates.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(candidates.map((c) => c.id)));
    }
  };

  const bulkAction = (status: string) => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    bulkMutation.mutate({ ids, status });
  };

  const openPreview = async (candidateId: number) => {
    setPreviewLoading(candidateId);
    setError(null);
    try {
      const data = await api.getListingPreview(candidateId);
      setPreview(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Preview failed');
    } finally {
      setPreviewLoading(null);
    }
  };

  const bulkPublish = () => {
    const approvedIds = Array.from(selected).filter((id) =>
      candidates.find((c) => c.id === id && c.status === 'approved')
    );
    if (approvedIds.length === 0) {
      setError('No approved candidates selected for publishing.');
      return;
    }
    publishMutation.mutate(approvedIds);
  };

  const selectedCount = selected.size;
  const selectedApprovedCount = Array.from(selected).filter((id) =>
    candidates.find((c) => c.id === id && c.status === 'approved')
  ).length;
  const displayError = error || queryError?.message || null;

  return (
    <div>
      <h2 class="page-title">Candidates</h2>

      <StatusTabs statuses={STATUSES} current={filter} onChange={setFilter} />

      <Alerts notice={notice} error={displayError} />

      {selectedCount > 0 && (
        <div
          class="card"
          style="margin-bottom:1rem;padding:0.75rem 1rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap"
        >
          <span style="font-weight:600">{selectedCount} selected</span>
          <button
            class="btn btn-success btn-sm"
            onClick={() => bulkAction('approved')}
            disabled={bulkMutation.isPending}
          >
            Bulk Approve
          </button>
          <button
            class="btn btn-danger btn-sm"
            onClick={() => bulkAction('rejected')}
            disabled={bulkMutation.isPending}
          >
            Bulk Reject
          </button>
          {selectedApprovedCount > 0 && (
            <button
              class="btn btn-primary btn-sm"
              onClick={bulkPublish}
              disabled={publishMutation.isPending}
            >
              {publishMutation.isPending
                ? 'Publishing...'
                : `Publish ${selectedApprovedCount} to eBay`}
            </button>
          )}
          <button class="btn btn-sm" onClick={() => setSelected(new Set())}>
            Clear
          </button>
        </div>
      )}

      {preview && (
        <PreviewPanel
          preview={preview}
          onClose={() => setPreview(null)}
          onPublish={() => publishMutation.mutate([preview.candidate_id])}
          publishing={publishMutation.isPending}
        />
      )}

      {isLoading ? (
        <div class="loading">Loading...</div>
      ) : (
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width:40px">
                  <input
                    type="checkbox"
                    checked={
                      candidates.length > 0 &&
                      selected.size === candidates.length
                    }
                    onChange={toggleAll}
                  />
                </th>
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
                <tr key={c.id} class={selected.has(c.id) ? 'row-selected' : ''}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(c.id)}
                      onChange={() => toggleSelect(c.id)}
                    />
                  </td>
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
                    {c.status === 'approved' && (
                      <button
                        class="btn btn-primary btn-sm"
                        onClick={() => openPreview(c.id)}
                        disabled={previewLoading === c.id}
                      >
                        {previewLoading === c.id ? 'Loading...' : 'Preview'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {candidates.length === 0 && (
                <EmptyRow colspan={13} message="No candidates found" />
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PreviewPanel({
  preview,
  onClose,
  onPublish,
  publishing,
}: {
  preview: ListingPreview;
  onClose: () => void;
  onPublish: () => void;
  publishing: boolean;
}) {
  const profit = preview.estimated_profit_jpy;
  return (
    <div class="card" style="margin-bottom:1.5rem">
      <div class="section-head">
        <h3>Listing Preview - {preview.title_jp}</h3>
        <button class="btn btn-sm" onClick={onClose}>
          Close
        </button>
      </div>
      <div class="preview-grid">
        <div class="preview-row">
          <span class="preview-label">SKU</span>
          <span>{preview.sku}</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">Source</span>
          <span>{preview.source_site}</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">Cost</span>
          <span>{formatJpy(preview.cost_jpy)}</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">Listing Price</span>
          <span style="font-weight:700;font-size:1.1rem">
            {formatUsd(preview.listing_price_usd)}
          </span>
        </div>
        <div class="preview-row">
          <span class="preview-label">FX Rate</span>
          <span>{preview.fx_rate} JPY/USD</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">eBay Fee</span>
          <span>{formatJpy(preview.ebay_fee_jpy)}</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">Payoneer Fee</span>
          <span>{formatJpy(preview.payoneer_fee_jpy)}</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">Shipping</span>
          <span>{formatJpy(preview.shipping_cost_jpy)}</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">Packing</span>
          <span>{formatJpy(preview.packing_cost_jpy)}</span>
        </div>
        <div class="preview-row">
          <span class="preview-label">Est. Profit</span>
          <span
            style={`font-weight:700;font-size:1.1rem;color:${profitColor(profit)}`}
          >
            {formatJpy(profit)}
          </span>
        </div>
      </div>
      <div style="margin-top:1rem;display:flex;gap:0.75rem">
        <button
          class="btn btn-primary"
          onClick={onPublish}
          disabled={publishing || preview.status !== 'approved'}
        >
          {publishing ? 'Publishing...' : 'Publish to eBay'}
        </button>
        <button class="btn btn-secondary" onClick={onClose}>
          Cancel
        </button>
      </div>
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
