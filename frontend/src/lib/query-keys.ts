export const queryKeys = {
  dashboard: ['dashboard'] as const,
  candidates: (status: string | null) => ['candidates', status] as const,
  orders: (status: string | null) => ['orders', status] as const,
  messages: (buyer: string | undefined, category?: string | undefined) =>
    ['messages', buyer, category] as const,
  researchRuns: ['researchRuns'] as const,
  researchRun: (id: number) => ['researchRun', id] as const,
  listingLimits: ['listingLimits'] as const,
  jobRuns: ['jobRuns'] as const,
  systemHealth: ['systemHealth'] as const,
  schedulerStatus: ['schedulerStatus'] as const,
};
