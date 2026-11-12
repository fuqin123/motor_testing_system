import type {
  Alarm,
  AlarmList,
  DevicesResponse,
  MotorCard,
  Overview,
  PeerAnalysis,
  QuadrantAnalysis,
  SelfAnalysis,
  SeriesPoint,
  SettingsResponse,
  SystemInfo,
  TrendAnalysis,
  TrendSeries,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
  })
  if (!response.ok) {
    let detail = `请求失败 (${response.status})`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      // ignore non-json error body
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value))
    }
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  overview: () => request<Overview>('/dashboard/overview'),
  dashboardTrend: (range: string, motorCode?: string | null) =>
    request<TrendSeries>(`/dashboard/trend${query({ range, motor_id: motorCode || undefined })}`),
  motors: () => request<{ items: MotorCard[]; total: number }>('/motors'),
  motor: (code: string) =>
    request<{
      motor: MotorCard
      sensors: import('./types').SensorInfo[]
      baseline: import('./types').Baseline | null
      recent_alarms: Alarm[]
    }>(`/motors/${encodeURIComponent(code)}`),
  motorSeries: (code: string, range: string) =>
    request<{ motor_code: string; range: string; bucket_minutes: number; points: SeriesPoint[] }>(
      `/motors/${encodeURIComponent(code)}/series${query({ range })}`,
    ),
  selfAnalysis: (motorCode: string, range = '30d') =>
    request<SelfAnalysis>(`/analysis/self${query({ motor_id: motorCode, range })}`),
  peers: (group?: string) => request<PeerAnalysis>(`/analysis/peers${query({ group })}`),
  quadrant: () => request<QuadrantAnalysis>('/analysis/quadrant'),
  analysisTrend: (motorCode: string, range = '7d') =>
    request<TrendAnalysis>(`/analysis/trend${query({ motor_id: motorCode, range })}`),
  alarms: (params: {
    level?: string
    status?: string
    q?: string
    page?: number
    page_size?: number
  }) => request<AlarmList>(`/alarms${query(params)}`),
  alarm: (id: number) => request<Alarm>(`/alarms/${id}`),
  ackAlarm: (id: number) => request<Alarm>(`/alarms/${id}/ack`, { method: 'POST' }),
  closeAlarm: (id: number, solution: string) =>
    request<Alarm>(`/alarms/${id}/close`, {
      method: 'POST',
      body: JSON.stringify({ solution }),
    }),
  bulkClose: (ids: number[], solution: string) =>
    request<{ closed: number; items: Alarm[] }>('/alarms/bulk-close', {
      method: 'POST',
      body: JSON.stringify({ ids, solution }),
    }),
  deleteAlarm: (id: number) =>
    request<{ deleted: boolean; id: number }>(`/alarms/${id}`, { method: 'DELETE' }),
  alarmExport: async (params: { level?: string; status?: string; q?: string }): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/alarms/export.csv${query(params)}`)
    if (!response.ok) {
      throw new ApiError(response.status, '导出失败')
    }
    return response.blob()
  },
  devices: () => request<DevicesResponse>('/devices'),
  pollGateway: (code: string) =>
    request<{ accepted: boolean; message: string }>(
      `/devices/gateways/${encodeURIComponent(code)}/poll`,
      { method: 'POST' },
    ),
  collectorPoll: () =>
    request<{ accepted: boolean; message: string }>('/system/collector/poll', {
      method: 'POST',
    }),
  settings: () => request<SettingsResponse>('/settings'),
  updateNotifications: (payload: Record<string, unknown>) =>
    request<import('./types').NotificationSettings>('/settings/notifications', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  updateThresholds: (code: string, payload: Record<string, unknown>) =>
    request<ThresholdResponse>(`/motors/${encodeURIComponent(code)}/thresholds`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  testFeishu: () =>
    request<{ status: string; attempts: number; response_code: number | null; detail: string }>(
      '/settings/feishu/test',
      { method: 'POST' },
    ),
  systemInfo: () => request<SystemInfo>('/system/info'),
  me: () => request<{ name: string; role: string; auth_mode: string }>('/system/me'),
}

export interface ThresholdResponse {
  code: string
  temp_limit_c: number
  current_limit_a: number
  temp_deviation_pct: number
  current_deviation_pct: number
  rise_rate_limit_c_per_day: number
  notify_enabled: boolean
  pilot: boolean
}
