import { render } from '@testing-library/preact';
import { describe, expect, it } from 'vitest';
import { Badge } from '../Badge';

describe('Badge', () => {
  it('renders status text', () => {
    const { getByText } = render(<Badge status="approved" />);
    expect(getByText('approved')).toBeInTheDocument();
  });

  it('applies status as CSS class by default', () => {
    const { getByText } = render(<Badge status="pending" />);
    const el = getByText('pending');
    expect(el).toHaveClass('badge', 'pending');
  });

  it('uses custom class when provided', () => {
    const { getByText } = render(<Badge status="active" class="badge-info" />);
    const el = getByText('active');
    expect(el).toHaveClass('badge', 'badge-info');
  });
});
