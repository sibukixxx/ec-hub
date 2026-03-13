import { useState } from 'preact/hooks';
import { api } from '../api';

export function ProfitCalc() {
  const [form, setForm] = useState({
    cost_jpy: 3000,
    ebay_price_usd: 50,
    weight_g: 500,
    destination: 'US',
  });
  const [result, setResult] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: name === 'destination' ? value : Number(value) }));
  };

  const calculate = async () => {
    const data = await api.calcProfit(form);
    setResult(data);
  };

  return (
    <div>
      <h2 class="page-title">Profit Calculator</h2>

      <div class="card" style="margin-bottom:1.5rem">
        <div class="calc-form">
          <div>
            <label>Cost (JPY)</label>
            <input type="number" name="cost_jpy" value={form.cost_jpy} onInput={handleChange} />
          </div>
          <div>
            <label>eBay Price (USD)</label>
            <input type="number" name="ebay_price_usd" value={form.ebay_price_usd} onInput={handleChange} />
          </div>
          <div>
            <label>Weight (g)</label>
            <input type="number" name="weight_g" value={form.weight_g} onInput={handleChange} />
          </div>
          <div>
            <label>Destination</label>
            <input type="text" name="destination" value={form.destination} onInput={handleChange} />
          </div>
        </div>
        <button class="btn btn-primary" onClick={calculate}>Calculate</button>
      </div>

      {result && (
        <div class="card">
          <table>
            <tbody>
              <tr><td>Revenue (JPY)</td><td style="text-align:right">{'\u00a5'}{result.jpy_revenue.toLocaleString()}</td></tr>
              <tr><td>FX Rate</td><td style="text-align:right">{result.fx_rate.toFixed(2)}</td></tr>
              <tr style="border-top:1px solid var(--border)"><td>Cost</td><td style="text-align:right">{'\u00a5'}{result.jpy_cost.toLocaleString()}</td></tr>
              <tr><td>eBay Fee</td><td style="text-align:right">{'\u00a5'}{result.ebay_fee.toLocaleString()}</td></tr>
              <tr><td>Payoneer Fee</td><td style="text-align:right">{'\u00a5'}{result.payoneer_fee.toLocaleString()}</td></tr>
              <tr><td>Shipping</td><td style="text-align:right">{'\u00a5'}{result.shipping_cost.toLocaleString()}</td></tr>
              <tr><td>Packing</td><td style="text-align:right">{'\u00a5'}{result.packing_cost.toLocaleString()}</td></tr>
              <tr><td>FX Buffer</td><td style="text-align:right">{'\u00a5'}{result.fx_buffer.toLocaleString()}</td></tr>
              <tr style="border-top:2px solid var(--border)">
                <td><strong>Net Profit</strong></td>
                <td style={`text-align:right;font-size:1.2rem;color:${result.net_profit >= 0 ? 'var(--green)' : 'var(--red)'}`}>
                  <strong>{'\u00a5'}{result.net_profit.toLocaleString()}</strong>
                </td>
              </tr>
              <tr>
                <td><strong>Margin Rate</strong></td>
                <td style={`text-align:right;font-size:1.2rem;color:${result.margin_rate >= 0.3 ? 'var(--green)' : 'var(--red)'}`}>
                  <strong>{(result.margin_rate * 100).toFixed(1)}%</strong>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
