import { useMutation } from '@tanstack/react-query';
import type { RoutableProps } from 'preact-router';
import { useState } from 'preact/hooks';
import { api } from '../api';
import { profitColor } from '../lib/color';
import { formatJpy } from '../lib/format';
import type { ProfitForm, ProfitResult } from '../types';

export function ProfitCalc(_props: RoutableProps) {
  const [form, setForm] = useState<ProfitForm>({
    cost_jpy: 3000,
    ebay_price_usd: 50,
    weight_g: 500,
    destination: 'US',
  });

  const calcMutation = useMutation({
    mutationFn: (data: ProfitForm) => api.calcProfit(data),
  });

  const handleChange = (e: Event) => {
    const target = e.target as HTMLInputElement;
    const { name, value } = target;
    setForm((f) => ({
      ...f,
      [name]: name === 'destination' ? value : Number(value),
    }));
  };

  return (
    <div>
      <h2 class="page-title">Profit Calculator</h2>

      <div class="card" style="margin-bottom:1.5rem">
        <div class="calc-form">
          <FormField
            label="Cost (JPY)"
            name="cost_jpy"
            type="number"
            value={form.cost_jpy}
            onChange={handleChange}
          />
          <FormField
            label="eBay Price (USD)"
            name="ebay_price_usd"
            type="number"
            value={form.ebay_price_usd}
            onChange={handleChange}
          />
          <FormField
            label="Weight (g)"
            name="weight_g"
            type="number"
            value={form.weight_g}
            onChange={handleChange}
          />
          <FormField
            label="Destination"
            name="destination"
            type="text"
            value={form.destination}
            onChange={handleChange}
          />
        </div>
        <button
          class="btn btn-primary"
          onClick={() => calcMutation.mutate(form)}
          disabled={calcMutation.isPending}
        >
          {calcMutation.isPending ? 'Calculating...' : 'Calculate'}
        </button>
      </div>

      {calcMutation.data && <ProfitBreakdown result={calcMutation.data} />}
    </div>
  );
}

interface FormFieldProps {
  label: string;
  name: string;
  type: string;
  value: number | string;
  onChange: (e: Event) => void;
}

function FormField({ label, name, type, value, onChange }: FormFieldProps) {
  return (
    <div>
      <label>{label}</label>
      <input type={type} name={name} value={value} onInput={onChange} />
    </div>
  );
}

function ProfitBreakdown({ result }: { result: ProfitResult }) {
  const rows: Array<{
    label: string;
    value: string;
    separator?: boolean;
    highlight?: boolean;
  }> = [
    { label: 'Revenue (JPY)', value: formatJpy(result.jpy_revenue) },
    { label: 'FX Rate', value: result.fx_rate.toFixed(2) },
    {
      label: 'Cost',
      value: formatJpy(result.jpy_cost),
      separator: true,
    },
    { label: 'eBay Fee', value: formatJpy(result.ebay_fee) },
    { label: 'Payoneer Fee', value: formatJpy(result.payoneer_fee) },
    { label: 'Shipping', value: formatJpy(result.shipping_cost) },
    { label: 'Packing', value: formatJpy(result.packing_cost) },
    { label: 'FX Buffer', value: formatJpy(result.fx_buffer) },
  ];

  return (
    <div class="card">
      <table>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.label}
              style={row.separator ? 'border-top:1px solid var(--border)' : ''}
            >
              <td>{row.label}</td>
              <td style="text-align:right">{row.value}</td>
            </tr>
          ))}
          <tr style="border-top:2px solid var(--border)">
            <td>
              <strong>Net Profit</strong>
            </td>
            <td
              style={`text-align:right;font-size:1.2rem;color:${profitColor(result.net_profit)}`}
            >
              <strong>{formatJpy(result.net_profit)}</strong>
            </td>
          </tr>
          <tr>
            <td>
              <strong>Margin Rate</strong>
            </td>
            <td
              style={`text-align:right;font-size:1.2rem;color:${result.margin_rate >= 0.3 ? 'var(--green)' : 'var(--red)'}`}
            >
              <strong>{(result.margin_rate * 100).toFixed(1)}%</strong>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
