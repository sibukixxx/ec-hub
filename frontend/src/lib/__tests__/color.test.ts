import { describe, expect, it } from 'vitest';
import {
  healthBadge,
  marginColor,
  matchScoreColor,
  profitColor,
  runStatusBadge,
} from '../color';

describe('marginColor', () => {
  it('returns green for margin >= 0.3', () => {
    expect(marginColor(0.3)).toBe('var(--green)');
    expect(marginColor(0.5)).toBe('var(--green)');
  });

  it('returns yellow for margin >= 0.15 and < 0.3', () => {
    expect(marginColor(0.15)).toBe('var(--yellow)');
    expect(marginColor(0.25)).toBe('var(--yellow)');
  });

  it('returns red for margin < 0.15', () => {
    expect(marginColor(0.1)).toBe('var(--red)');
    expect(marginColor(0)).toBe('var(--red)');
  });
});

describe('matchScoreColor', () => {
  it('returns green for score >= 60', () => {
    expect(matchScoreColor(60)).toBe('var(--green)');
    expect(matchScoreColor(100)).toBe('var(--green)');
  });

  it('returns yellow for score >= 40 and < 60', () => {
    expect(matchScoreColor(40)).toBe('var(--yellow)');
    expect(matchScoreColor(59)).toBe('var(--yellow)');
  });

  it('returns dim for score < 40', () => {
    expect(matchScoreColor(39)).toBe('var(--text-dim)');
    expect(matchScoreColor(0)).toBe('var(--text-dim)');
  });
});

describe('profitColor', () => {
  it('returns green for positive values', () => {
    expect(profitColor(100)).toBe('var(--green)');
  });

  it('returns green for zero', () => {
    expect(profitColor(0)).toBe('var(--green)');
  });

  it('returns red for negative values', () => {
    expect(profitColor(-1)).toBe('var(--red)');
  });
});

describe('runStatusBadge', () => {
  it('returns completed class when completed', () => {
    expect(runStatusBadge(true)).toBe('completed');
  });

  it('returns awaiting_purchase class when not completed', () => {
    expect(runStatusBadge(false)).toBe('awaiting_purchase');
  });
});

describe('healthBadge', () => {
  it('returns approved for ok status', () => {
    expect(healthBadge('ok')).toBe('approved');
  });

  it('returns awaiting_purchase for degraded status', () => {
    expect(healthBadge('degraded')).toBe('awaiting_purchase');
  });

  it('returns rejected for other statuses', () => {
    expect(healthBadge('error')).toBe('rejected');
    expect(healthBadge('down')).toBe('rejected');
  });
});
