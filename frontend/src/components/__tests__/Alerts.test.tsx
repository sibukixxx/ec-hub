import { render } from '@testing-library/preact';
import { describe, expect, it } from 'vitest';
import { Alerts } from '../Alerts';

describe('Alerts', () => {
  it('renders nothing when both are null', () => {
    const { container } = render(<Alerts notice={null} error={null} />);
    expect(container.textContent).toBe('');
  });

  it('renders success alert when notice is provided', () => {
    const { getByText } = render(<Alerts notice="Done!" error={null} />);
    const el = getByText('Done!');
    expect(el).toHaveClass('alert', 'alert-success');
  });

  it('renders danger alert when error is provided', () => {
    const { getByText } = render(<Alerts notice={null} error="Failed!" />);
    const el = getByText('Failed!');
    expect(el).toHaveClass('alert', 'alert-danger');
  });

  it('renders both alerts simultaneously', () => {
    const { getByText } = render(<Alerts notice="Success" error="Warning" />);
    expect(getByText('Success')).toBeInTheDocument();
    expect(getByText('Warning')).toBeInTheDocument();
  });
});
