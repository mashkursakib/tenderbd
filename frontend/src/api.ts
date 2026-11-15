// Fetch wrapper for the TenderBD API (SPEC.md section 4).
// Base /api/v1. Auth: Bearer token from localStorage 'tenderbd_token'.

import type {
  AdminOverview,
  AlertsResponse,
  AlertPrefs,
  AuthResponse,
  CompanyProfile,
  ConsultingRequest,
  DocumentItem,
  Evaluation,
  FavouritesResponse,
  JvMessage,
  JvPost,
  JvRoom,
  Me,
  PaymentSubmission,
  RefreshSummary,
  RoomMessagesResponse,
  Stats,
  Summary,
  Tender,
  TenderListResponse,
} from './types';

export const TOKEN_KEY = 'tenderbd_token';
const BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage unavailable; session just won't persist.
  }
}

function detailFromBody(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const d = (body as { detail?: unknown }).detail;
    if (typeof d === 'string' && d) return d;
    if (Array.isArray(d)) {
      const msgs = d
        .map((item) =>
          item && typeof item === 'object' && 'msg' in item
            ? String((item as { msg?: unknown }).msg)
            : '',
        )
        .filter(Boolean);
      if (msgs.length) return msgs.join(' ');
    }
  }
  return fallback;
}

interface ReqOptions {
  method?: string;
  body?: unknown;
  /** Skip the Authorization header even when a token exists. */
  noAuth?: boolean;
  /** Send as FormData (for uploads); body must already be FormData. */
  formData?: boolean;
}

async function req<T>(path: string, opts: ReqOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (!opts.formData) headers['Content-Type'] = 'application/json';
  if (!opts.noAuth) {
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: opts.method ?? 'GET',
      headers,
      body: opts.formData
        ? (opts.body as FormData)
        : opts.body !== undefined
          ? JSON.stringify(opts.body)
          : undefined,
    });
  } catch {
    throw new ApiError(0, 'Could not reach the server. Check your connection and try again.');
  }
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!res.ok) {
    throw new ApiError(
      res.status,
      detailFromBody(body, `Request failed (${res.status}).`),
    );
  }
  return body as T;
}

export interface TenderQuery {
  q?: string;
  work_types?: string[];
  departments?: string[];
  division?: string;
  district?: string;
  value_min?: number;
  value_max?: number;
  statuses?: string[];
  method?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}

function buildTenderQuery(params: TenderQuery): string {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  (params.work_types ?? []).forEach((v) => qs.append('work_types[]', v));
  (params.departments ?? []).forEach((v) => qs.append('departments[]', v));
  if (params.division) qs.set('division', params.division);
  if (params.district) qs.set('district', params.district);
  if (params.value_min !== undefined) qs.set('value_min', String(params.value_min));
  if (params.value_max !== undefined) qs.set('value_max', String(params.value_max));
  (params.statuses ?? []).forEach((v) => qs.append('statuses[]', v));
  if (params.method) qs.set('method', params.method);
  if (params.sort) qs.set('sort', params.sort);
  if (params.limit !== undefined) qs.set('limit', String(params.limit));
  if (params.offset !== undefined) qs.set('offset', String(params.offset));
  const s = qs.toString();
  return s ? `?${s}` : '';
}

export const api = {
  // Public.
  getStats: () => req<Stats>('/stats'),
  listTenders: (params: TenderQuery) =>
    req<TenderListResponse>(`/tenders${buildTenderQuery(params)}`),
  getTender: (id: number) => req<Tender>(`/tenders/${id}`),
  // Refresh needs a refresh token the browser does not have; call it
  // without the auth header and surface whatever the server returns.
  refresh: (body: { days: number; max_pages: number; enrich_limit: number }) =>
    req<RefreshSummary>('/refresh', { method: 'POST', body, noAuth: true }),

  // Auth.
  signup: (name: string, email: string, password: string) =>
    req<AuthResponse>('/auth/signup', { method: 'POST', body: { name, email, password } }),
  signin: (email: string, password: string) =>
    req<AuthResponse>('/auth/signin', { method: 'POST', body: { email, password } }),
  signout: () => req<Record<string, never>>('/auth/signout', { method: 'POST', body: {} }),
  me: () => req<Me>('/auth/me'),
  requestPasswordReset: (email: string) =>
    req<{ message: string }>('/auth/request-password-reset', {
      method: 'POST',
      body: { email },
    }),
  resetPassword: (email: string, reset_token: string, new_password: string) =>
    req<AuthResponse>('/auth/reset-password', {
      method: 'POST',
      body: { email, reset_token, new_password },
    }),

  // Tender features.
  evaluate: (id: number) =>
    req<Evaluation>(`/tenders/${id}/evaluate`, { method: 'POST', body: {} }),
  summarize: (id: number, lang: 'en' | 'bn') =>
    req<Summary>(`/tenders/${id}/summarize`, { method: 'POST', body: { lang } }),

  // Profile / vault.
  getCompany: () => req<CompanyProfile | null>('/profile/company'),
  saveCompany: (profile: Partial<CompanyProfile>) =>
    req<CompanyProfile>('/profile/company', { method: 'PUT', body: profile }),
  listDocuments: () => req<DocumentItem[]>('/documents'),
  uploadDocument: (file: File, docType: string) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('doc_type', docType);
    return req<DocumentItem>('/documents', { method: 'POST', body: fd, formData: true });
  },
  deleteDocument: (id: number) =>
    req<Record<string, never>>(`/documents/${id}`, { method: 'DELETE' }),
  async downloadDocument(id: number): Promise<string> {
    const headers: Record<string, string> = {};
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${BASE}/documents/${id}/download`, { headers });
    if (!res.ok) {
      let msg = `Download failed (${res.status}).`;
      try {
        const body = await res.json();
        msg = detailFromBody(body, msg);
      } catch {
        // Keep the fallback message.
      }
      throw new ApiError(res.status, msg);
    }
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  },

  // Favourites.
  listFavourites: () => req<FavouritesResponse>('/favourites'),
  toggleFavourite: (tenderId: number) =>
    req<{ favourite: boolean }>(`/favourites/${tenderId}/toggle`, {
      method: 'POST',
      body: {},
    }),
  setStage: (tenderId: number, stage: string) =>
    req<FavouritesResponse['favourites'][number]>(`/favourites/${tenderId}/stage`, {
      method: 'PATCH',
      body: { stage },
    }),

  // Alerts.
  getAlerts: () => req<AlertsResponse>('/alerts'),
  saveAlerts: (prefs: AlertPrefs) =>
    req<AlertPrefs>('/alerts', { method: 'PUT', body: prefs }),

  // JV room.
  listJvPosts: () => req<JvPost[]>('/jv/posts'),
  createJvPost: (body: {
    title: string;
    need_description: string;
    looking_for?: string;
    share_offered?: string;
    tender_id?: number | null;
  }) => req<JvPost>('/jv/posts', { method: 'POST', body }),
  expressInterest: (postId: number, message: string) =>
    req<Record<string, never>>(`/jv/posts/${postId}/interest`, {
      method: 'POST',
      body: { message },
    }),
  openRoom: (postId: number) =>
    req<JvRoom>(`/jv/posts/${postId}/room`, { method: 'POST', body: {} }),
  getRoomMessages: (roomId: number) =>
    req<RoomMessagesResponse>(`/jv/rooms/${roomId}/messages`),
  sendRoomMessage: (roomId: number, bodyText: string) =>
    req<JvMessage>(`/jv/rooms/${roomId}/messages`, {
      method: 'POST',
      body: { body: bodyText },
    }),

  // Payments / consulting.
  listMyPayments: () => req<PaymentSubmission[]>('/payments/mine'),
  submitPayment: (body: {
    plan: string;
    method: string;
    transaction_id: string;
    sender_number?: string;
  }) => req<PaymentSubmission>('/payments', { method: 'POST', body }),
  listMyConsulting: () => req<ConsultingRequest[]>('/consulting/mine'),
  createConsulting: (body: {
    topic: string;
    message: string;
    tender_id?: number | null;
  }) => req<ConsultingRequest>('/consulting', { method: 'POST', body }),

  // Admin.
  adminOverview: () => req<AdminOverview>('/admin/overview'),
  reviewPayment: (id: number, approve: boolean, note?: string) =>
    req<PaymentSubmission>(`/admin/payments/${id}/review`, {
      method: 'POST',
      body: { approve, note: note ?? '' },
    }),
  replyConsulting: (id: number, reply: string) =>
    req<ConsultingRequest>(`/admin/consulting/${id}/reply`, {
      method: 'POST',
      body: { reply },
    }),
  setUserPlan: (id: number, plan: string) =>
    req<Record<string, unknown>>(`/admin/users/${id}/plan`, {
      method: 'POST',
      body: { plan },
    }),
};
