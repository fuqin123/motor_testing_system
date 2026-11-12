import { defineStore } from 'pinia'

import { api } from '@/api/client'
import type { MotorCard, Overview, PilotInfo, SystemInfo } from '@/api/types'
import { useUiStore } from './ui'

const DEFAULT_USER = { name: '设备科 · 观察员', role: '观察员' }

export const useAppStore = defineStore('app', {
  state: () => ({
    meta: null as SystemInfo | null,
    overview: null as Overview | null,
    motors: [] as MotorCard[],
    loading: false,
    error: '',
    searchQuery: '',
    metaFetchedAt: 0,
    timer: null as number | null,
  }),
  getters: {
    user(state) {
      return state.meta?.user || state.overview?.user || DEFAULT_USER
    },
    alarmCount(state): number {
      return state.overview?.kpis.active_alarms ?? 0
    },
    criticalCount(state): number {
      return state.overview?.kpis.critical_alarms ?? 0
    },
    pilot(state): PilotInfo | null {
      return state.meta?.pilot || state.overview?.pilot || null
    },
    intervalMinutes(state): number {
      return (
        state.meta?.sampling.interval_minutes ?? state.overview?.sampling.interval_minutes ?? 15
      )
    },
    feishuConfigured(state): boolean {
      return state.meta?.feishu.configured ?? false
    },
    filteredMotors(state): MotorCard[] {
      const query = state.searchQuery.trim().toLowerCase()
      if (!query) return state.motors
      return state.motors.filter((motor) =>
        `${motor.code} ${motor.name} ${motor.location} ${motor.group}`
          .toLowerCase()
          .includes(query),
      )
    },
  },
  actions: {
    async fetchMeta(force = false) {
      if (!force && this.meta && Date.now() - this.metaFetchedAt < 5 * 60 * 1000) return
      try {
        this.meta = await api.systemInfo()
        this.metaFetchedAt = Date.now()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '系统信息加载失败'
      }
    },
    async fetchOverview(silent = false) {
      if (!silent) this.loading = true
      try {
        const data = await api.overview()
        this.overview = data
        this.motors = data.motors
        this.error = ''
      } catch (error) {
        const message = error instanceof Error ? error.message : '监测数据加载失败'
        this.error = message
        if (!silent) useUiStore().notify('err', '数据加载失败', message)
      } finally {
        this.loading = false
      }
    },
    async refresh() {
      await Promise.all([this.fetchOverview(true), this.fetchMeta()])
    },
    startPolling() {
      this.stopPolling()
      this.timer = window.setInterval(() => {
        if (document.visibilityState === 'visible') {
          void this.refresh()
        }
      }, 60_000)
    },
    stopPolling() {
      if (this.timer) {
        window.clearInterval(this.timer)
        this.timer = null
      }
    },
  },
})
