import { useState } from 'preact/hooks';
import { api } from '../api';

export function Compare() {
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const search = async () => {
    if (!keyword.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.comparePrice(keyword.trim());
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') search();
  };

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
              onInput={(e) => setKeyword(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Nintendo Switch, MUJI aroma"
            />
          </div>
          <button class="btn btn-primary" onClick={search} disabled={loading}>
            {loading ? 'Searching...' : 'Compare'}
          </button>
        </div>
      </div>

      {error && <div class="card" style="color:var(--red)">{error}</div>}

      {result && (
        <div>
          <div class="card" style="margin-bottom:0.5rem;padding:0.75rem 1rem">
            <span style="color:var(--text-dim)">
              FX Rate: <strong>{result.fx_rate.toFixed(2)}</strong> JPY/USD
              {' | '}eBay: <strong>{result.ebay_items.length}</strong> items
              {' | '}Source: <strong>{result.source_candidates.length}</strong> candidates
            </span>
          </div>

          {/* eBay listings */}
          <h3 style="margin:1.5rem 0 0.75rem">eBay Listings</h3>
          {result.ebay_items.length === 0 ? (
            <div class="card" style="color:var(--text-dim)">No eBay listings found</div>
          ) : (
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
                  {result.ebay_items.map((item) => (
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
                        <a href={item.url} target="_blank" rel="noopener" style="color:var(--blue)">
                          {item.title?.substring(0, 60)}{item.title?.length > 60 ? '...' : ''}
                        </a>
                      </td>
                      <td style="text-align:right;font-weight:600;color:var(--blue)">
                        ${item.price_usd?.toFixed(2) ?? '-'}
                      </td>
                      <td style="text-align:right">
                        {'\u00a5'}{item.price_jpy?.toLocaleString() ?? '-'}
                      </td>
                      <td>
                        <span class={`badge ${item.condition === 'NEW' ? 'badge-info' : ''}`}>
                          {item.condition || '-'}
                        </span>
                      </td>
                      <td>
                        {item.shipping?.free
                          ? <span style="color:var(--green)">Free</span>
                          : item.shipping?.cost != null
                            ? `$${item.shipping.cost.toFixed(2)}`
                            : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Source candidates comparison */}
          <h3 style="margin:1.5rem 0 0.75rem">Source Candidates (DB)</h3>
          {result.source_candidates.length === 0 ? (
            <div class="card" style="color:var(--text-dim)">
              No matching candidates in database. Run research first to populate data.
            </div>
          ) : (
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
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {result.source_candidates.map((c) => {
                    const margin = c.margin_rate ?? 0;
                    const marginColor = margin >= 0.3 ? 'var(--green)' : margin >= 0.15 ? 'var(--yellow)' : 'var(--red)';
                    return (
                      <tr key={c.id}>
                        <td>{c.title_jp?.substring(0, 40)}{c.title_jp?.length > 40 ? '...' : ''}</td>
                        <td><span class="badge">{c.source_site}</span></td>
                        <td style="text-align:right">{'\u00a5'}{c.cost_jpy?.toLocaleString()}</td>
                        <td style="text-align:right;color:var(--blue)">${c.ebay_price_usd?.toFixed(2)}</td>
                        <td style={`text-align:right;color:${(c.net_profit_jpy ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'}`}>
                          {'\u00a5'}{(c.net_profit_jpy ?? 0).toLocaleString()}
                        </td>
                        <td style={`text-align:right;font-weight:600;color:${marginColor}`}>
                          {(margin * 100).toFixed(1)}%
                        </td>
                        <td><span class={`badge badge-${c.status === 'approved' ? 'success' : c.status === 'rejected' ? 'danger' : 'info'}`}>{c.status}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Quick comparison summary */}
          {result.ebay_items.length > 0 && (
            <div class="card" style="margin-top:1.5rem">
              <h3 style="margin-bottom:0.75rem">Summary</h3>
              <ComparisonSummary ebayItems={result.ebay_items} candidates={result.source_candidates} fxRate={result.fx_rate} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ComparisonSummary({ ebayItems, candidates, fxRate }) {
  const ebayPrices = ebayItems.filter((i) => i.price_usd).map((i) => i.price_usd);
  const avgEbay = ebayPrices.length > 0 ? ebayPrices.reduce((a, b) => a + b, 0) / ebayPrices.length : 0;
  const minEbay = ebayPrices.length > 0 ? Math.min(...ebayPrices) : 0;
  const maxEbay = ebayPrices.length > 0 ? Math.max(...ebayPrices) : 0;

  const sourceCosts = candidates.filter((c) => c.cost_jpy).map((c) => c.cost_jpy);
  const avgCost = sourceCosts.length > 0 ? sourceCosts.reduce((a, b) => a + b, 0) / sourceCosts.length : 0;

  const potentialMargin = avgEbay > 0 && avgCost > 0
    ? ((avgEbay * fxRate - avgCost) / avgCost * 100)
    : null;

  return (
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:1rem">
      <div>
        <div style="color:var(--text-dim);font-size:0.85rem">eBay Avg Price</div>
        <div style="font-size:1.3rem;font-weight:700;color:var(--blue)">${avgEbay.toFixed(2)}</div>
      </div>
      <div>
        <div style="color:var(--text-dim);font-size:0.85rem">eBay Price Range</div>
        <div style="font-size:1.1rem">${minEbay.toFixed(2)} - ${maxEbay.toFixed(2)}</div>
      </div>
      {avgCost > 0 && (
        <div>
          <div style="color:var(--text-dim);font-size:0.85rem">Avg Source Cost</div>
          <div style="font-size:1.3rem;font-weight:700">{'\u00a5'}{Math.round(avgCost).toLocaleString()}</div>
        </div>
      )}
      {potentialMargin !== null && (
        <div>
          <div style="color:var(--text-dim);font-size:0.85rem">Potential Margin</div>
          <div style={`font-size:1.3rem;font-weight:700;color:${potentialMargin >= 30 ? 'var(--green)' : potentialMargin >= 15 ? 'var(--yellow)' : 'var(--red)'}`}>
            {potentialMargin.toFixed(1)}%
          </div>
        </div>
      )}
    </div>
  );
}
