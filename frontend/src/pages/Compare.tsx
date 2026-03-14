import { useMutation } from '@tanstack/react-query';
import type { RoutableProps } from 'preact-router';
import { useState } from 'preact/hooks';
import { api } from '../api';
import { Badge } from '../components/Badge';
import { marginColor, matchScoreColor } from '../lib/color';
import { formatJpy, formatUsd, inputValue, truncate } from '../lib/format';
import type { EbayItem, SourceCandidate } from '../types';

export function Compare(_props: RoutableProps) {
  const [keyword, setKeyword] = useState('');

  const searchMutation = useMutation({
    mutationFn: (kw: string) => api.comparePrice(kw),
  });

  const search = () => {
    if (!keyword.trim()) return;
    searchMutation.mutate(keyword.trim());
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') search();
  };

  const result = searchMutation.data ?? null;

  return (
    <div>
      <h2 class="page-title">Price Compare</h2>

      <div class="card" style="margin-bottom:1.5rem">
        <div style="display:flex;gap:0.5rem;align-items:flex-end">
          <div style="flex:1">
            <label>Search Keyword</label>
            <input
              type="text"
              value={keyword}
              onInput={(e) => setKeyword(inputValue(e))}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Nintendo Switch, MUJI aroma"
            />
          </div>
          <button
            class="btn btn-primary"
            onClick={search}
            disabled={searchMutation.isPending}
          >
            {searchMutation.isPending ? 'Searching...' : 'Compare'}
          </button>
        </div>
      </div>

      {searchMutation.error && (
        <div class="card" style="color:var(--red)">
          {(searchMutation.error as Error).message}
        </div>
      )}

      {result && (
        <div>
          <div class="card" style="margin-bottom:0.5rem;padding:0.75rem 1rem">
            <span style="color:var(--text-dim)">
              FX Rate: <strong>{result.fx_rate.toFixed(2)}</strong> JPY/USD
              {' | '}eBay: <strong>{result.ebay_items.length}</strong> items
              {' | '}Source: <strong>{result.source_candidates.length}</strong>{' '}
              candidates
            </span>
          </div>

          <h3 style="margin:1.5rem 0 0.75rem">eBay Listings</h3>
          <EbayItemsTable items={result.ebay_items} />

          <h3 style="margin:1.5rem 0 0.75rem">Source Candidates (DB)</h3>
          <SourceCandidatesTable candidates={result.source_candidates} />

          {result.ebay_items.length > 0 && (
            <div class="card" style="margin-top:1.5rem">
              <h3 style="margin-bottom:0.75rem">Summary</h3>
              <ComparisonSummary
                ebayItems={result.ebay_items}
                candidates={result.source_candidates}
                fxRate={result.fx_rate}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EbayItemsTable({ items }: { items: EbayItem[] }) {
  if (items.length === 0) {
    return (
      <div class="card" style="color:var(--text-dim)">
        No eBay listings found
      </div>
    );
  }

  return (
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Title</th>
            <th style="text-align:right">Price (USD)</th>
            <th style="text-align:right">Price (JPY)</th>
            <th>Condition</th>
            <th>Shipping</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.item_id}>
              <td style="width:50px">
                {item.image_url && (
                  <img
                    src={item.image_url}
                    alt=""
                    style="width:40px;height:40px;object-fit:cover;border-radius:4px"
                  />
                )}
              </td>
              <td>
                <a
                  href={item.url || '#'}
                  target="_blank"
                  rel="noopener"
                  style="color:var(--blue)"
                >
                  {truncate(item.title, 60)}
                </a>
              </td>
              <td style="text-align:right;font-weight:600;color:var(--blue)">
                {formatUsd(item.price_usd)}
              </td>
              <td style="text-align:right">{formatJpy(item.price_jpy)}</td>
              <td>
                <Badge
                  status={item.condition || '-'}
                  class={item.condition === 'NEW' ? 'badge-info' : ''}
                />
              </td>
              <td>
                {item.shipping?.free ? (
                  <span style="color:var(--green)">Free</span>
                ) : item.shipping?.cost != null ? (
                  formatUsd(item.shipping.cost)
                ) : (
                  '-'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SourceCandidatesTable({
  candidates,
}: {
  candidates: SourceCandidate[];
}) {
  if (candidates.length === 0) {
    return (
      <div class="card" style="color:var(--text-dim)">
        No matching candidates in database. Run research first to populate data.
      </div>
    );
  }

  return (
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Source</th>
            <th style="text-align:right">Cost (JPY)</th>
            <th style="text-align:right">eBay Price</th>
            <th style="text-align:right">Profit</th>
            <th style="text-align:right">Margin</th>
            <th style="text-align:right">Match</th>
            <th>Why</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => {
            const margin = c.margin_rate ?? 0;
            const matchScore = c.compare_match_score ?? c.match_score;
            const matchReason = c.compare_match_reason || c.match_reason;
            return (
              <tr key={c.id}>
                <td>{truncate(c.title_jp, 40)}</td>
                <td>
                  <Badge status={c.source_site} />
                </td>
                <td style="text-align:right">{formatJpy(c.cost_jpy)}</td>
                <td style="text-align:right;color:var(--blue)">
                  {formatUsd(c.ebay_price_usd)}
                </td>
                <td
                  style={`text-align:right;color:${(c.net_profit_jpy ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'}`}
                >
                  {formatJpy(c.net_profit_jpy ?? 0)}
                </td>
                <td
                  style={`text-align:right;font-weight:600;color:${marginColor(margin)}`}
                >
                  {(margin * 100).toFixed(1)}%
                </td>
                <td
                  style={`text-align:right;font-weight:700;color:${matchScoreColor(matchScore ?? 0)}`}
                >
                  {matchScore != null ? `${matchScore}/100` : '-'}
                </td>
                <td
                  title={matchReason || ''}
                  style="max-width:260px;color:var(--text-dim);font-size:0.85rem"
                >
                  {truncate(matchReason, 70)}
                </td>
                <td>
                  <Badge
                    status={c.status}
                    class={`badge-${c.status === 'approved' ? 'success' : c.status === 'rejected' ? 'danger' : 'info'}`}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface ComparisonSummaryProps {
  ebayItems: EbayItem[];
  candidates: SourceCandidate[];
  fxRate: number;
}

function ComparisonSummary({
  ebayItems,
  candidates,
  fxRate,
}: ComparisonSummaryProps) {
  const ebayPrices = ebayItems
    .filter((i) => i.price_usd)
    .map((i) => i.price_usd!);
  const avgEbay =
    ebayPrices.length > 0
      ? ebayPrices.reduce((a, b) => a + b, 0) / ebayPrices.length
      : 0;
  const minEbay = ebayPrices.length > 0 ? Math.min(...ebayPrices) : 0;
  const maxEbay = ebayPrices.length > 0 ? Math.max(...ebayPrices) : 0;

  const sourceCosts = candidates
    .filter((c) => c.cost_jpy)
    .map((c) => c.cost_jpy!);
  const avgCost =
    sourceCosts.length > 0
      ? sourceCosts.reduce((a, b) => a + b, 0) / sourceCosts.length
      : 0;

  const potentialMargin =
    avgEbay > 0 && avgCost > 0
      ? ((avgEbay * fxRate - avgCost) / avgCost) * 100
      : null;

  return (
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:1rem">
      <div>
        <div style="color:var(--text-dim);font-size:0.85rem">
          eBay Avg Price
        </div>
        <div style="font-size:1.3rem;font-weight:700;color:var(--blue)">
          {formatUsd(avgEbay)}
        </div>
      </div>
      <div>
        <div style="color:var(--text-dim);font-size:0.85rem">
          eBay Price Range
        </div>
        <div style="font-size:1.1rem">
          {formatUsd(minEbay)} - {formatUsd(maxEbay)}
        </div>
      </div>
      {avgCost > 0 && (
        <div>
          <div style="color:var(--text-dim);font-size:0.85rem">
            Avg Source Cost
          </div>
          <div style="font-size:1.3rem;font-weight:700">
            {formatJpy(Math.round(avgCost))}
          </div>
        </div>
      )}
      {potentialMargin !== null && (
        <div>
          <div style="color:var(--text-dim);font-size:0.85rem">
            Potential Margin
          </div>
          <div
            style={`font-size:1.3rem;font-weight:700;color:${marginColor(potentialMargin / 100)}`}
          >
            {potentialMargin.toFixed(1)}%
          </div>
        </div>
      )}
    </div>
  );
}
