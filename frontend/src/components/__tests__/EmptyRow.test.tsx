import { render } from '@testing-library/preact';
import { describe, expect, it } from 'vitest';
import { EmptyRow } from '../EmptyRow';

describe('EmptyRow', () => {
  it('renders message in a table cell', () => {
    const { getByText } = render(
      <table>
        <tbody>
          <EmptyRow colspan={5} message="No data found" />
        </tbody>
      </table>
    );
    expect(getByText('No data found')).toBeInTheDocument();
  });

  it('sets correct colspan', () => {
    const { container } = render(
      <table>
        <tbody>
          <EmptyRow colspan={8} message="Empty" />
        </tbody>
      </table>
    );
    const td = container.querySelector('td');
    expect(td?.getAttribute('colspan')).toBe('8');
  });
});
