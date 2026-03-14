import type {
  Candidate,
  CompareResult,
  DashboardData,
  JobRun,
  ListingLimits,
  ListingPreview,
  Message,
  Order,
  ProfitForm,
  ProfitResult,
  ResearchRun,
  SchedulerStatus,
  ServiceHealth,
} from './types';

const BASE = '/api';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

function withParams(
  path: string,
  params: Record<string, string | number | null | undefined>
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export const api = {
  getDashboard: () => request<DashboardData>('/dashboard'),

  getCandidates: (status?: string | null, limit = 50) =>
    request<Candidate[]>(withParams('/candidates', { status, limit })),

  updateCandidateStatus: (id: number, status: string) =>
    request<void>(`/candidates/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  bulkUpdateCandidateStatus: (ids: number[], status: string) =>
    request<{ updated_count: number; status: string }>('/candidates/bulk-status', {
      method: 'POST',
      body: JSON.stringify({ ids, status }),
    }),

  getOrders: (status?: string | null, limit = 50) =>
    request<Order[]>(withParams('/orders', { status, limit })),

  updateOrderStatus: (id: number, data: Record<string, unknown>) =>
    request<void>(`/orders/${id}/status`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  checkOrders: () =>
    request<{ new_orders: number }>('/orders/check', { method: 'POST' }),

  calcProfit: (data: ProfitForm) =>
    request<ProfitResult>('/calc/profit', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  comparePrice: (keyword: string, maxResults = 5) =>
    request<CompareResult>('/compare', {
      method: 'POST',
      body: JSON.stringify({ keyword, max_results: maxResults }),
    }),

  predictPrice: (data: Record<string, unknown>) =>
    request<unknown>('/predict/price', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getResearchRuns: (limit = 20) =>
    request<ResearchRun[]>(withParams('/research/runs', { limit })),

  getResearchRun: (id: number) => request<ResearchRun>(`/research/runs/${id}`),

  runResearch: (data: { keywords?: string[]; pages: number }) =>
    request<{ run_id: number }>('/research/run', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  runListing: (candidateIds?: number[]) =>
    request<{ listed_count: number }>('/listing/run', {
      method: 'POST',
      body: candidateIds ? JSON.stringify({ candidate_ids: candidateIds }) : undefined,
    }),

  getListingPreview: (candidateId: number) =>
    request<ListingPreview>(`/listing/preview/${candidateId}`),

  getListingLimits: () => request<ListingLimits>('/listing/limits'),

  getMessages: (buyer?: string, category?: string, limit = 50) =>
    request<Message[]>(withParams('/messages', { buyer, category, limit })),

  replyMessage: (id: number, body: string) =>
    request<void>(`/messages/${id}/reply`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),

  getJobRuns: (jobName?: string | null, limit = 20) =>
    request<JobRun[]>(withParams('/job-runs', { job_name: jobName, limit })),

  getSystemHealth: () => request<ServiceHealth[]>('/system/health'),

  getSchedulerStatus: () => request<SchedulerStatus>('/scheduler/status'),

  triggerSchedulerJob: (jobName: string) =>
    request<void>(`/scheduler/trigger/${jobName}`, { method: 'POST' }),

  exportUrl: (dataType: string, format = 'csv') =>
    `${BASE}${withParams(`/export/${dataType}`, { format })}`,
};
