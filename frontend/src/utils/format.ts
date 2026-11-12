import type { AlarmLevel, AlarmStatus, MotorStatus, NotificationStatus } from '@/api/types'

export function fmt(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return Number(value).toFixed(digits)
}

export function signed(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${value >= 0 ? '+' : ''}${Number(value).toFixed(digits)}`
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function average(values: number[]): number | null {
  if (!values.length) return null
  return values.reduce((sum, item) => sum + item, 0) / values.length
}

export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function timeAgo(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return '—'
  const minutes = Math.floor((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  return `${Math.floor(hours / 24)} 天前`
}

export function hhmm(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return '—'
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

export function mmdd(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return '—'
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export function mmddhhmm(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return '—'
  return `${mmdd(value)} ${hhmm(value)}`
}

export function dateTime(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return '—'
  const pad = (item: number) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

export const STATUS_TEXT: Record<MotorStatus, string> = {
  ok: '正常',
  warn: '警告',
  crit: '严重',
  unknown: '未接入',
}

export const LEVEL_TEXT: Record<AlarmLevel, string> = {
  crit: '严重',
  warn: '警告',
  info: '提示',
}

export const ALARM_STATUS_TEXT: Record<AlarmStatus, string> = {
  open: '未处理',
  ack: '处理中',
  closed: '已闭环',
}

export const NOTIFICATION_TEXT: Record<NotificationStatus, string> = {
  pending: '待发送',
  sent: '已送达',
  failed: '发送失败',
  skipped: '未通知',
}

export function statusClass(status: MotorStatus): 'ok' | 'warn' | 'crit' | 'mut' {
  if (status === 'ok') return 'ok'
  if (status === 'warn') return 'warn'
  if (status === 'crit') return 'crit'
  return 'mut'
}

export function pointLabel(ts: string, range: string): string {
  if (range === '24h') return hhmm(ts)
  if (range === '7d') return mmddhhmm(ts)
  return mmdd(ts)
}

export function rangeDays(range: string): number {
  if (range === '7d') return 7
  if (range === '30d') return 30
  return 1
}

export function formatValue(value: number | null, unit: string, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${fmt(value, digits)} ${unit}`.trim()
}

export function formatMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  if (value < 60) return `${Math.round(value)} min`
  return `${(value / 60).toFixed(1)} h`
}

export function acceptanceClass(status: string): string {
  if (status === 'pass') return 'ok'
  if (status === 'fail') return 'crit'
  if (status === 'pending') return 'warn'
  return 'mut'
}
