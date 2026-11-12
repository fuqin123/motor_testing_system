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
  overview: (date?: string) => request<Overview>(`/dashboard/overview${query({ date })}`),
  dashboardTrend: (range: string, motorCode?: string | null, date?: string) =>
    request<TrendSeries>(
      `/dashboard/trend${query({ range, motor_id: motorCode || undefined, date })}`,
    ),
  motors: (includeDisabled = false) =>
    request<{ items: MotorCard[]; total: number }>(
      `/motors${query({ include_disabled: includeDisabled ? 'true' : undefined })}`,
    ),
  motor: (code: string, date?: string) =>
    request<{
      motor: MotorCard
      sensors: import('./types').SensorInfo[]
      baseline: import('./types').Baseline | null
      recent_alarms: Alarm[]
    }>(`/motors/${encodeURIComponent(code)}${query({ date })}`),
  motorSeries: (code: string, range: string, date?: string) =>
    request<{
      motor_code: string
      range: string
      bucket_minutes: number
      points: SeriesPoint[]
      date?: string
      is_today?: boolean
    }>(`/motors/${encodeURIComponent(code)}/series${query({ range, date })}`),
  selfAnalysis: (motorCode: string, range = '30d', date?: string) =>
    request<SelfAnalysis>(`/analysis/self${query({ motor_id: motorCode, range, date })}`),
  peers: (group?: string, date?: string) =>
    request<PeerAnalysis>(`/analysis/peers${query({ group, date })}`),
  quadrant: (date?: string) =>
    request<QuadrantAnalysis>(`/analysis/quadrant${query({ date })}`),
  analysisTrend: (motorCode: string, range = '7d', date?: string) =>
    request<TrendAnalysis>(`/analysis/trend${query({ motor_id: motorCode, range, date })}`),
  upsertMotor: (payload: import('./types').MotorConfigPayload) =>
    request<{ code: string; name: string; enabled: boolean; created: boolean }>('/motors', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  upsertGateway: (payload: import('./types').GatewayConfigPayload) =>
    request<{ created: boolean; gateway: import('./types').GatewayInfo }>('/devices/gateways', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteGateway: (code: string) =>
    request<{ deleted: boolean; code: string }>(
      `/devices/gateways/${encodeURIComponent(code)}`,
      { method: 'DELETE' },
    ),
  upsertSensor: (payload: import('./types').SensorConfigPayload) =>
    request<{ created: boolean; sensor: import('./types').SensorInfo }>('/devices/sensors', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteSensor: (id: number) =>
    request<{ deleted: boolean; id: number }>(`/devices/sensors/${id}`, {
      method: 'DELETE',
    }),
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
