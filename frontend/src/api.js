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

export const api = {
  getDashboard: () => request('/dashboard'),

  getCandidates: (status, limit = 50) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    params.set('limit', limit);
    return request(`/candidates?${params}`);
  },

  updateCandidateStatus: (id, status) =>
    request(`/candidates/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  getOrders: (status, limit = 50) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    params.set('limit', limit);
    return request(`/orders?${params}`);
  },

  calcProfit: (data) =>
    request('/calc/profit', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
