import { describe, expect, it } from 'vitest';
import {
  formatDate,
  formatJpy,
  formatTimestamp,
  formatUsd,
  truncate,
} from '../format';

describe('formatJpy', () => {
  it('returns formatted yen string for positive number', () => {
    expect(formatJpy(12345)).toBe('\u00a512,345');
  });

  it('returns formatted yen string for zero', () => {
    expect(formatJpy(0)).toBe('\u00a50');
  });

  it('returns dash for null', () => {
    expect(formatJpy(null)).toBe('-');
  });

  it('returns dash for undefined', () => {
    expect(formatJpy(undefined)).toBe('-');
  });

  it('returns formatted yen string for negative number', () => {
    expect(formatJpy(-500)).toBe('\u00a5-500');
  });
});

describe('formatUsd', () => {
  it('returns formatted dollar string with two decimals', () => {
    expect(formatUsd(12.5)).toBe('$12.50');
  });

  it('returns formatted dollar string for zero', () => {
    expect(formatUsd(0)).toBe('$0.00');
  });

  it('returns dash for null', () => {
    expect(formatUsd(null)).toBe('-');
  });

  it('returns dash for undefined', () => {
    expect(formatUsd(undefined)).toBe('-');
  });
});

describe('truncate', () => {
  it('returns full text when shorter than maxLen', () => {
    expect(truncate('hello', 10)).toBe('hello');
  });

  it('truncates with ellipsis when text exceeds maxLen', () => {
    expect(truncate('hello world foo bar', 10)).toBe('hello worl...');
  });

  it('returns dash for null', () => {
    expect(truncate(null, 10)).toBe('-');
  });

  it('returns dash for undefined', () => {
    expect(truncate(undefined, 10)).toBe('-');
  });

  it('returns dash for empty string', () => {
    expect(truncate('', 10)).toBe('-');
  });

  it('returns full text when exactly maxLen', () => {
    expect(truncate('12345', 5)).toBe('12345');
  });
});

describe('formatTimestamp', () => {
  it('formats ISO timestamp to YYYY-MM-DD HH:MM', () => {
    expect(formatTimestamp('2026-03-15T14:30:00Z')).toBe('2026-03-15 14:30');
  });

  it('returns dash for null', () => {
    expect(formatTimestamp(null)).toBe('-');
  });

  it('returns dash for undefined', () => {
    expect(formatTimestamp(undefined)).toBe('-');
  });

  it('returns dash for empty string', () => {
    expect(formatTimestamp('')).toBe('-');
  });
});

describe('formatDate', () => {
  it('formats ISO date to YYYY-MM-DD', () => {
    expect(formatDate('2026-03-15T14:30:00Z')).toBe('2026-03-15');
  });

  it('returns dash for null', () => {
    expect(formatDate(null)).toBe('-');
  });

  it('returns dash for empty string', () => {
    expect(formatDate('')).toBe('-');
  });
});
