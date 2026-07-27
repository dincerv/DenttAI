/**
 * Merkezi API istemcisi.
 * - Access token'ı localStorage'dan otomatik ekler
 * - 401 gelirse önce refresh token ile yenileme dener
 * - Refresh da başarısız olursa token temizlenip login'e yönlendirilir
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { clearTokens, getAccessToken, getImpersonationToken, setTokens } from '@/lib/auth';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8081/api';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
  withCredentials: true,
});

let csrfToken: string | null = null;

async function ensureCsrfToken(): Promise<void> {
  if (csrfToken) return;
  const res = await axios.get(`${BASE_URL}/auth/health`, { withCredentials: true });
  csrfToken = (res.headers['x-csrf-token'] as string | undefined) ?? null;
}

// ── Request interceptor — Bearer token ekleme ─────────────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getImpersonationToken() || getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  const method = (config.method || '').toLowerCase();
  const hasRequestBody = config.data !== undefined && config.data !== null;
  const isMutating = ['post', 'put', 'patch', 'delete'].includes(method) || (!method && hasRequestBody);

  if (!isMutating) {
    return config;
  }

  return ensureCsrfToken().then(() => {
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
    return config;
  });
});

// ── Response interceptor — 401 → token refresh, sonra retry ──
let _isRefreshing = false;
let _refreshQueue: Array<(token: string) => void> = [];

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry && typeof window !== 'undefined') {

      // Eş zamanlı birden fazla istek 401 alırsa yalnızca bir refresh yapılır
      if (_isRefreshing) {
        return new Promise((resolve) => {
          _refreshQueue.push((newToken) => {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            resolve(apiClient(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      _isRefreshing = true;

      try {
        await ensureCsrfToken();
        const refreshHeaders = csrfToken ? { 'X-CSRF-Token': csrfToken } : undefined;
        const res = await axios.post(
          `${BASE_URL}/auth/refresh`,
          {},
          { withCredentials: true, headers: refreshHeaders },
        );
        const { access_token, refresh_token: newRefresh } = res.data;
        setTokens(access_token, newRefresh);
        apiClient.defaults.headers.common.Authorization = `Bearer ${access_token}`;
        _refreshQueue.forEach((cb) => cb(access_token));
        _refreshQueue = [];
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
      } catch {
        clearTokens();
        _refreshQueue = [];
        window.location.href = '/login';
        return Promise.reject(error);
      } finally {
        _isRefreshing = false;
      }
    }

    if (error.response?.status === 403 && typeof window !== 'undefined' && !originalRequest._retry) {
      const data = error.response.data;
      const detail = typeof data === 'string'
        ? data.toLowerCase()
        : (data as { detail?: string } | undefined)?.detail?.toLowerCase() || '';
      const reqMethod = (originalRequest.method || '').toLowerCase();
      const reqUrl = (originalRequest.url || '').toLowerCase();
      const isMutatingRequest = ['post', 'put', 'patch', 'delete'].includes(reqMethod);
      const isLoginRoute = reqUrl.includes('/auth/login');

      if (detail.includes('csrf') || (isLoginRoute && isMutatingRequest)) {
        originalRequest._retry = true;
        csrfToken = null;
        await ensureCsrfToken();
        if (csrfToken) {
          originalRequest.headers['X-CSRF-Token'] = csrfToken;
        }
        return apiClient(originalRequest);
      }
    }

    return Promise.reject(error);
  },
);

// ── Endpoint helper'ları ───────────────────────────────────

export const authApi = {
  login:   (email: string, password: string, clinicCode?: string) =>
    apiClient.post('/auth/login', { email, password, clinic_code: clinicCode?.toUpperCase() || undefined }),
  me:      () => apiClient.get('/auth/me'),
  logout:  () => apiClient.post('/auth/logout', {}),
};

export const appointmentApi = {
  list:    (params?: Record<string, string>) =>
    apiClient.get('/appointments', { params }),
  create:  (data: unknown) => apiClient.post('/appointments', data),
  update:  (id: string, data: unknown) => apiClient.patch(`/appointments/${id}`, data),
  delete:  (id: string) => apiClient.delete(`/appointments/${id}`),
  cancel:  (id: string) => apiClient.patch(`/appointments/${id}`, { status: 'cancelled' }),
  doctors: () => apiClient.get('/appointments/doctors'),
  patients: (params?: { q?: string; limit?: number }) => apiClient.get('/appointments/patients', { params }),
  createPatient: (data: { full_name: string; phone: string; email?: string }) =>
    apiClient.post('/appointments/patients', data),
  updatePatient: (id: string, data: { full_name?: string; phone?: string }) =>
    apiClient.patch(`/appointments/patients/${id}`, data),
};

export const waitlistApi = {
  list:   () => apiClient.get('/waitlist'),
  add:    (data: unknown) => apiClient.post('/waitlist', data),
  remove: (id: string) => apiClient.delete(`/waitlist/${id}`),
};

export const patientNotesApi = {
  create: (data: { patient_id: string; note_type?: string; content: string; appointment_id?: string }) =>
    apiClient.post('/patient-notes', data),
  list: (params?: Record<string, string>) =>
    apiClient.get('/patient-notes', { params }),
  myLog: (params?: Record<string, string>) =>
    apiClient.get('/patient-notes/my-log', { params }),
  allLog: (params?: Record<string, string>) =>
    apiClient.get('/patient-notes/all-log', { params }),
};

export const inventoryApi = {
  listItems:        () => apiClient.get('/inventory/items'),
  batchSummaries:   () => apiClient.get('/inventory/items/batches'),
  createItem:       (data: unknown) => apiClient.post('/inventory/items', data),
  updateItem:       (id: string, data: unknown) => apiClient.patch(`/inventory/items/${id}`, data),
  deleteItem:       (id: string) => apiClient.delete(`/inventory/items/${id}`),
  adjustQuantity:   (id: string, delta: number, reason?: string) =>
    apiClient.post(`/inventory/items/${id}/adjust`, { delta, reason }),
  getHistory:       (id: string) => apiClient.get(`/inventory/items/${id}/history`),
  generateQr:       (data: unknown) => apiClient.post('/inventory/qr/generate', data),
  activateQr:       (qrId: string) => apiClient.post('/inventory/qr/activate', { qr_id: qrId }),
  listCycles:       (params?: Record<string, string>) =>
    apiClient.get('/inventory/cycle', { params }),
  endCycle:         (data: unknown) => apiClient.post('/inventory/cycle/end', data),
};

export const analyticsApi = {
  recoveredRevenue:  (params?: Record<string, string>) =>
    apiClient.get('/analytics/revenue/recovered', { params }),
  appointmentStats:  (params?: Record<string, string>) =>
    apiClient.get('/analytics/appointments/stats', { params }),
  wasteReport:       () => apiClient.get('/analytics/inventory/waste-report'),
  doctorPerformance: (params?: Record<string, string>) =>
    apiClient.get('/analytics/doctors/performance', { params }),
  newPatientsOverview: (params?: Record<string, string>) =>
    apiClient.get('/analytics/patients/new-overview', { params }),
  expiringCycles:    () => apiClient.get('/analytics/inventory/expiring-cycles'),
  treatmentCounts:   (params?: Record<string, string>) =>
    apiClient.get('/analytics/treatments/counts', { params }),
  treatmentsByDoctor: (params?: Record<string, string>) =>
    apiClient.get('/analytics/treatments/by-doctor', { params }),
  aiChat: (message: string, params?: Record<string, string>) =>
    apiClient.post('/analytics/ai/chat', { message }, { params }),
  aiInsights: (params?: Record<string, string>) =>
    apiClient.get('/analytics/ai/insights', { params }),
};

export const usersApi = {
  list:   () => apiClient.get('/auth/users'),
  create: (data: { email: string; full_name: string; password: string; role: string }) =>
    apiClient.post('/auth/users', data),
  update: (id: string, data: { role?: string; is_active?: boolean; full_name?: string }) =>
    apiClient.patch(`/auth/users/${id}`, data),
  remove: (id: string) => apiClient.delete(`/auth/users/${id}`),
  changePassword: (id: string, newPassword: string) =>
    apiClient.patch(`/auth/users/${id}/password`, { new_password: newPassword }),
  updatePermissions: (id: string, allowedPages: string[]) =>
    apiClient.patch(`/auth/users/${id}/permissions`, { allowed_pages: allowedPages }),
};

export const adminApi = {
  listClinics:  () => apiClient.get('/auth/admin/clinics'),
  listUsers:    (clinicId: string) => apiClient.get(`/auth/admin/clinics/${clinicId}/users`),
  addUser: (clinicId: string, data: {
    email: string;
    full_name: string;
    password: string;
    role: string;
  }) => apiClient.post(`/auth/admin/clinics/${clinicId}/users`, data),
  createClinic: (data: {
    clinic_name: string;
    clinic_code?: string;
    owner_email?: string;
    owner_password?: string;
    owner_full_name?: string;
  }) => apiClient.post('/auth/admin/clinics', data),
  updateClinic: (id: string, data: { name?: string; is_active?: boolean }) =>
    apiClient.patch(`/auth/admin/clinics/${id}`, data),
  deleteClinic: (id: string) => apiClient.delete(`/auth/admin/clinics/${id}`),
  getStats: () => apiClient.get('/auth/admin/stats'),
  getAIUsage: (period: 'day' | 'week' | 'month' | 'year') =>
    apiClient.get('/auth/admin/ai-usage', { params: { period } }),
  impersonateClinic: (id: string) => apiClient.post(`/auth/admin/clinics/${id}/impersonate`),
};

export const tenantsApi = {
  getMyClinic: () => apiClient.get('/tenants/me'),
};

export const integrationApi = {
  providers:       () => apiClient.get('/integration/providers'),
  listConfigs:     () => apiClient.get('/integration/config'),
  createConfig:    (data: { provider: string; display_name: string; config: Record<string, string>; sync_interval_minutes?: number }) =>
    apiClient.post('/integration/config', data),
  updateConfig:    (id: string, data: { display_name?: string; config?: Record<string, string>; is_active?: boolean; sync_interval_minutes?: number }) =>
    apiClient.patch(`/integration/config/${id}`, data),
  updateSessionCookie: (id: string, session_cookie: string) =>
    apiClient.patch(`/integration/config/${id}/session`, { session_cookie }),
  getDoctorMappings: (id: string) =>
    apiClient.get(`/integration/config/${id}/doctor-mappings`),
  updateDoctorMappings: (id: string, mappings: Record<string, string | null>) =>
    apiClient.patch(`/integration/config/${id}/doctor-mappings`, { mappings }),
  deleteConfig:    (id: string) => apiClient.delete(`/integration/config/${id}`),
  triggerSync:     () => apiClient.post('/integration/sync'),
  triggerPostOpReachout: (appointmentId: string) =>
    apiClient.post(`/integration/appointments/${appointmentId}/post-op-reachout`),
  testConnection:  () => apiClient.post('/integration/test-connection'),
};



