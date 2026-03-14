import { fireEvent, render } from '@testing-library/preact';
import { describe, expect, it, vi } from 'vitest';
import { StatusTabs } from '../StatusTabs';

describe('StatusTabs', () => {
  const statuses: Array<string | null> = [null, 'pending', 'approved'];

  it('renders all status buttons', () => {
    const { getByText } = render(
      <StatusTabs statuses={statuses} current={null} onChange={() => {}} />
    );
    expect(getByText('All')).toBeInTheDocument();
    expect(getByText('pending')).toBeInTheDocument();
    expect(getByText('approved')).toBeInTheDocument();
  });

  it('marks current tab as active', () => {
    const { getByText } = render(
      <StatusTabs statuses={statuses} current="pending" onChange={() => {}} />
    );
    expect(getByText('pending')).toHaveClass('active');
    expect(getByText('All')).not.toHaveClass('active');
  });

  it('calls onChange when a tab is clicked', () => {
    const onChange = vi.fn();
    const { getByText } = render(
      <StatusTabs statuses={statuses} current={null} onChange={onChange} />
    );
    fireEvent.click(getByText('approved'));
    expect(onChange).toHaveBeenCalledWith('approved');
  });

  it('uses custom formatLabel when provided', () => {
    const { getByText } = render(
      <StatusTabs
        statuses={[null, 'awaiting_purchase']}
        current={null}
        onChange={() => {}}
        formatLabel={(s) => (s ? s.replace(/_/g, ' ').toUpperCase() : 'ALL')}
      />
    );
    expect(getByText('ALL')).toBeInTheDocument();
    expect(getByText('AWAITING PURCHASE')).toBeInTheDocument();
  });
});
