const BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

function withParams(path, params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, value);
    }
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

export const api = {
  getDashboard: () => request('/dashboard'),

  getCandidates: (status, limit = 50) =>
    request(withParams('/candidates', { status, limit })),

  updateCandidateStatus: (id, status) =>
    request(`/candidates/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  getOrders: (status, limit = 50) =>
    request(withParams('/orders', { status, limit })),

  updateOrderStatus: (id, data) =>
    request(`/orders/${id}/status`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  checkOrders: () =>
    request('/orders/check', { method: 'POST' }),

  calcProfit: (data) =>
    request('/calc/profit', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  comparePrice: (keyword, maxResults = 5) =>
    request('/compare', {
      method: 'POST',
      body: JSON.stringify({ keyword, max_results: maxResults }),
    }),

  predictPrice: (data) =>
    request('/predict/price', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getResearchRuns: (limit = 20) =>
    request(withParams('/research/runs', { limit })),

  getResearchRun: (id) =>
    request(`/research/runs/${id}`),

  runResearch: (data) =>
    request('/research/run', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  runListing: () =>
    request('/listing/run', { method: 'POST' }),

  getListingLimits: () =>
    request('/listing/limits'),

  getMessages: (buyer, limit = 50) =>
    request(withParams('/messages', { buyer, limit })),

  replyMessage: (id, body) =>
    request(`/messages/${id}/reply`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),

  getJobRuns: (jobName, limit = 20) =>
    request(withParams('/job-runs', { job_name: jobName, limit })),

  getSystemHealth: () =>
    request('/system/health'),

  getSchedulerStatus: () =>
    request('/scheduler/status'),

  triggerSchedulerJob: (jobName) =>
    request(`/scheduler/trigger/${jobName}`, { method: 'POST' }),

  exportUrl: (dataType, format = 'csv') =>
    `${BASE}${withParams(`/export/${dataType}`, { format })}`,
};
