export type MotorStatus = 'ok' | 'warn' | 'crit' | 'unknown'
export type AlarmLevel = 'crit' | 'warn' | 'info'
export type AlarmStatus = 'open' | 'ack' | 'closed'
export type NotificationStatus = 'pending' | 'sent' | 'failed' | 'skipped'

export interface PilotInfo {
  start_date: string
  days: number
  current_day: number
  progress_pct: number
  remaining_days: number
  scope: string
}

export interface SamplingInfo {
  interval_minutes: number
  last_poll_at: string | null
  next_poll_at: string | null
  collector_mode: string
  collector_running: boolean
}

export interface LoraInfo {
  frequency_mhz: number
  baud_rate: number
  sf: number
  bw_khz: number
  cr: string
}

export interface FeishuInfo {
  configured: boolean
  masked_webhook: string
  group_name: string
}

export interface TimelineItem {
  key: string
  title: string
  detail: string
  ts: string | null
  state: string
}

export interface MotorSummary {
  code: string
  name: string
  location: string
  group: string
  rated_kw: number
  rated_current_a: number
  temp_limit_c: number
  current_limit_a: number
  pilot: boolean
  enabled: boolean
  node_code: string
  vfd_model: string
  install_date: string
  last_maintenance: string
  sensors: string
}

export interface MotorCard extends MotorSummary {
  status: MotorStatus
  online: boolean
  temperature_c: number | null
  current_avg_a: number | null
  current_a: number | null
  current_b: number | null
  current_c: number | null
  load_pct: number | null
  temp_deviation_pct: number | null
  last_seen_at: string | null
  quality: string | null
  spark_temp: number[]
  spark_current: number[]
}

export interface Alarm {
  id: number
  code: string
  level: AlarmLevel
  level_text: string
  title: string
  description: string
  advice: string
  motor_code: string | null
  motor_name: string | null
  device_code: string | null
  metric: string
  value: number | null
  threshold: number | null
  unit: string
  status: AlarmStatus
  owner: string
  notification_status: NotificationStatus
  notification_to: string
  triggered_at: string
  last_seen_at: string
  closed_at: string | null
  closed_by: string | null
  solution: string | null
  timeline: TimelineItem[]
  notification?: {
    id: number
    channel: string
    target: string
    status: string
    attempts: number
    response_code: number | null
    created_at: string
  } | null
}

export interface Overview {
  generated_at: string
  date: string
  is_today: boolean
  user: { name: string; role: string }
  sampling: SamplingInfo
  pilot: PilotInfo
  kpis: {
    online_motors: number
    total_motors: number
    active_alarms: number
    critical_alarms: number
    warning_alarms: number
    avg_temperature_c: number | null
    avg_load_pct: number | null
    link_availability_pct: number
    packets_today: number
    packet_loss_pct: number
    avg_latency_ms: number
  }
  motors: MotorCard[]
  active_alarms: Alarm[]
  link: {
    gateways_online: number
    gateways_total: number
    nodes_online: number
    nodes_total: number
    avg_rssi_dbm: number | null
    packets_today: number
    packet_loss_pct: number
    avg_latency_ms: number
  }
  loop: {
    notifications_today: number
    closed_today: number
    avg_response_min: number | null
    items: { text: string; who: string; ts: string }[]
  }
}

export interface SeriesPoint {
  ts: string
  temperature_c: number | null
  current_avg_a: number | null
  current_a: number | null
  current_b: number | null
  current_c: number | null
}

export interface TrendSeries {
  range: string
  bucket_minutes: number
  points: SeriesPoint[]
  motor_code: string | null
  date?: string
  is_today?: boolean
}

export interface Baseline {
  temp_median: number | null
  temp_p10: number | null
  temp_p90: number | null
  current_median: number | null
  current_p10: number | null
  current_p90: number | null
  sample_count: number
}

export interface AnalysisRule {
  key: string
  label: string
  hit: boolean
  detail: string
}

export interface Verdict {
  key: string
  text: string
  advice?: string
}

export interface SelfAnalysis {
  motor: MotorSummary
  range: string
  series: SeriesPoint[]
  band: { ts: string; lo: number | null; hi: number | null }[]
  baseline: Baseline | null
  latest: {
    temperature_c: number | null
    current_avg_a: number | null
    current_a: number | null
    current_b: number | null
    current_c: number | null
    load_pct: number | null
    quality: string | null
    ts: string | null
  }
  deviation: { temp_pct: number | null; current_pct: number | null }
  rise_rate_c_per_day: number | null
  rules: AnalysisRule[]
  verdict: Verdict
}

export interface PeerMotor {
  code: string
  name: string
  status: MotorStatus
  temperature_c: number | null
  current_avg_a: number | null
  current_a: number | null
  current_b: number | null
  current_c: number | null
  load_pct: number | null
  temp_deviation_pct: number | null
  current_deviation_pct: number | null
  score: number
  rank?: number
}

export interface PeerAnalysis {
  group: string
  groups: string[]
  motors: PeerMotor[]
  ranking: PeerMotor[]
  insight: string
}

export interface QuadrantPoint {
  code: string
  name: string
  temp_deviation_pct: number
  current_deviation_pct: number
  status: MotorStatus
}

export interface QuadrantAnalysis {
  points: QuadrantPoint[]
  thresholds: { temp_pct: number; current_pct: number }
}

export interface TrendAnalysis {
  motor: MotorSummary
  range: string
  series: SeriesPoint[]
  stats: {
    max_temp_c: number | null
    min_temp_c: number | null
    avg_temp_c: number | null
    slope_c_per_day: number | null
    sample_days: number
  }
  verdict: { bad: boolean; tag: string; text: string }
  events: { id: string; level: AlarmLevel; title: string; ts: string; status: AlarmStatus }[]
}

export interface AlarmList {
  items: Alarm[]
  total: number
  page: number
  page_size: number
  stats: { open: number; today: number; closed: number; avg_response_min: number | null }
}

export interface GatewayInfo {
  id: number
  code: string
  name: string
  host: string
  port: number
  framer: string
  enabled: boolean
  model: string
  firmware: string
  note: string
  online: boolean
  last_seen_at: string | null
  last_error: string | null
  consecutive_failures: number
  sensor_count: number
}

export interface SensorInfo {
  id: number
  code: string
  kind: 'temperature' | 'current'
  kind_text: string
  name: string
  motor_code: string | null
  motor_name: string | null
  gateway_code: string | null
  slave_id: number
  register_address: number
  register_count: number
  scale: number
  unit: string
  enabled: boolean
  power_type: string
  firmware: string
  signal_dbm: number | null
  snr_db: number | null
  online: boolean
  last_read_at: string | null
  last_error: string | null
  consecutive_failures: number
}

export interface DevicesResponse {
  summary: {
    gateways_online: number
    gateways_total: number
    sensors_total: number
    sensors_online: number
  }
  gateways: GatewayInfo[]
  sensors: SensorInfo[]
  events: { ts: string; level: string; text: string }[]
}

export interface NotificationSettings {
  critical_enabled: boolean
  warning_enabled: boolean
  info_enabled: boolean
  quiet_hours_enabled: boolean
  quiet_start: string
  quiet_end: string
  group_name: string
  owners: string[]
}

export interface ThresholdMotor {
  code: string
  name: string
  pilot: boolean
  enabled: boolean
  rated_current_a: number
  temp_limit_c: number
  current_limit_a: number
  temp_deviation_pct: number
  current_deviation_pct: number
  phase_imbalance_pct: number
  rise_rate_limit_c_per_day: number
  notify_enabled: boolean
}

export interface AcceptanceItem {
  key: string
  label: string
  status: 'pass' | 'fail' | 'manual' | 'pending'
  detail: string
}

export interface SettingsResponse {
  motors: ThresholdMotor[]
  notifications: NotificationSettings
  sampling: SamplingInfo
  lora: LoraInfo
  feishu: FeishuInfo
  pilot: PilotInfo
  acceptance: {
    items: AcceptanceItem[]
    generated_at: string
    pass_count: number
    total_auto: number
  }
}

export interface SystemInfo {
  app: { name: string; version: string; env: string; timezone: string }
  user: { name: string; role: string; auth_mode: string }
  counts: { motors: number; gateways: number; sensors: number }
  sampling: SamplingInfo
  collector: {
    thread_alive?: boolean
    running?: boolean
    last_error?: string | null
    last_cycle?: Record<string, unknown> | null
  }
  retention_days: number
  baseline_days: number
  lora: LoraInfo
  feishu: FeishuInfo
  pilot: PilotInfo
  acceptance: {
    items: AcceptanceItem[]
    generated_at: string
    pass_count: number
    total_auto: number
  }
  gateways: GatewayInfo[]
}

export interface MotorConfigPayload {
  code: string
  name: string
  location: string
  group_name: string
  rated_kw: number
  rated_current_a: number
  pilot: boolean
  enabled: boolean
  node_code: string
  vfd_model: string
  install_date: string
  last_maintenance: string
  temp_limit_c: number
  current_limit_a: number
  temp_deviation_pct: number
  current_deviation_pct: number
  phase_imbalance_pct: number
  rise_rate_limit_c_per_day: number
  notify_enabled: boolean
}

export interface GatewayConfigPayload {
  code: string
  name: string
  host: string
  port: number
  framer: 'rtu' | 'tcp'
  enabled: boolean
  model: string
  firmware: string
  note: string
}

export interface SensorConfigPayload {
  id?: number
  code?: string
  motor_code: string
  gateway_code: string
  kind: 'temperature' | 'current'
  name: string
  slave_id: number
  register_address: number
  register_count: number
  scale: number
  unit: string
  enabled: boolean
  power_type: string
  firmware: string
}
